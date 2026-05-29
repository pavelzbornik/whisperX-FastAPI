"""OpenAI Whisper-compatible synchronous audio transcription endpoints."""

import os
from datetime import datetime, timezone
from typing import Annotated, Any, NoReturn, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.api.dependencies import (
    get_alignment_service,
    get_file_service,
    get_task_repository,
    get_transcription_service,
)
from app.api.mappers import map_request_to_whisper_params
from app.api.schemas import (
    OpenAIJsonTranscriptionResponse,
    OpenAIResponseFormat,
    OpenAITranscriptionRequest,
    OpenAIVerboseJsonResponse,
    TimestampGranularity,
)
from app.audio import get_audio_duration, process_audio_file
from app.core.config import get_settings
from app.core.exceptions import (
    FileValidationError,
    UnsupportedFileExtensionError,
    ValidationError,
)
from app.core.gpu_semaphore import get_gpu_semaphore
from app.core.logging import logger
from app.domain.entities.task import Task as DomainTask
from app.domain.repositories.task_repository import ITaskRepository
from app.domain.services.alignment_service import IAlignmentService
from app.domain.services.transcription_service import ITranscriptionService
from app.files import ALLOWED_EXTENSIONS
from app.schemas import (
    AlignedTranscription,
    TaskEnum,
    TaskStatus,
    TaskType,
    VADOptions,
)
from app.services.file_service import FileService
from app.transcript import filter_aligned_transcription

_OPENAI_NON_JSON_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "Transcript in the requested format.",
        "content": {
            "application/json": {
                "schema": {
                    "oneOf": [
                        {
                            "$ref": "#/components/schemas/OpenAIJsonTranscriptionResponse"
                        },
                        {"$ref": "#/components/schemas/OpenAIVerboseJsonResponse"},
                    ]
                }
            },
            "text/plain": {"schema": {"type": "string"}},
            "application/x-subrip": {"schema": {"type": "string"}},
            "text/vtt": {"schema": {"type": "string"}},
        },
    },
}


def _validate_file_extension_or_raise_openai(
    file_service: FileService, filename: str
) -> None:
    """Validate the upload extension and re-raise as a domain exception.

    ``FileService.validate_file_extension`` raises ``fastapi.HTTPException`` for
    invalid extensions, which bypasses the project's exception handlers and would
    return FastAPI's default ``{"detail": ...}`` body instead of the OpenAI-style
    ``{"error": {"type": ...}}`` envelope. Convert it here so SDK clients still
    see a compatible error shape.
    """
    try:
        file_service.validate_file_extension(filename, ALLOWED_EXTENSIONS)
    except HTTPException as exc:
        raise UnsupportedFileExtensionError(
            filename=filename,
            extension=os.path.splitext(filename)[1].lower(),
            allowed=ALLOWED_EXTENSIONS,
        ) from exc


def _save_upload_or_raise_openai(
    file_service: FileService, file: StarletteUploadFile
) -> str:
    """Save the upload and re-raise FastAPI HTTP errors as domain exceptions."""
    try:
        return file_service.save_upload(cast(Any, file))
    except HTTPException as exc:
        raise FileValidationError(
            filename=file.filename or "unknown",
            reason=str(exc.detail),
        ) from exc


openai_compat_router = APIRouter(prefix="/v1", tags=["OpenAI compatibility"])


def _raise_openai_validation_error(message: str, field: str | None = None) -> NoReturn:
    """Raise a normalized validation error for OpenAI-compatible endpoints."""
    raise ValidationError(
        message=message,
        code="INVALID_OPENAI_REQUEST",
        user_message=message,
        field=field,
    )


async def _parse_openai_transcription_request(
    request: Request,
) -> tuple[OpenAITranscriptionRequest, StarletteUploadFile]:
    """Parse and validate OpenAI-compatible multipart form data."""
    form = await request.form()
    uploaded_file = form.get("file")
    if not isinstance(uploaded_file, StarletteUploadFile):
        _raise_openai_validation_error("The 'file' field is required.", field="file")

    payload = {
        "model": form.get("model"),
        "language": form.get("language"),
        "prompt": form.get("prompt"),
        "response_format": form.get("response_format", OpenAIResponseFormat.json.value),
        "temperature": form.get("temperature", 0.0),
        "timestamp_granularities": form.getlist("timestamp_granularities[]")
        or form.getlist("timestamp_granularities"),
    }

    try:
        return OpenAITranscriptionRequest.model_validate(payload), uploaded_file
    except PydanticValidationError as exc:
        _raise_openai_validation_error(str(exc))


def _format_timestamp(seconds: float, decimal_marker: str) -> str:
    """Format seconds as an SRT or VTT timestamp."""
    total_milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{decimal_marker}{milliseconds:03d}"


def _render_segments_as_subtitles(
    segments: list[dict[str, Any]],
    response_format: OpenAIResponseFormat,
) -> str:
    """Render transcript segments as SRT or VTT."""
    lines: list[str] = []
    if response_format == OpenAIResponseFormat.vtt:
        lines.append("WEBVTT")
        lines.append("")

    for index, segment in enumerate(segments, start=1):
        start = float(segment["start"])
        end = float(segment["end"])
        text = str(segment.get("text", "")).strip()
        if response_format == OpenAIResponseFormat.srt:
            lines.extend(
                [
                    str(index),
                    (
                        f"{_format_timestamp(start, ',')} --> "
                        f"{_format_timestamp(end, ',')}"
                    ),
                    text,
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    (
                        f"{_format_timestamp(start, '.')} --> "
                        f"{_format_timestamp(end, '.')}"
                    ),
                    text,
                    "",
                ]
            )

    return "\n".join(lines).strip()


def _build_text_from_transcript(transcript: dict[str, Any]) -> str:
    """Build transcript text from the transcription response."""
    text = str(transcript.get("text", "")).strip()
    if text:
        return text
    return " ".join(
        str(segment.get("text", "")).strip()
        for segment in transcript.get("segments", [])
        if str(segment.get("text", "")).strip()
    )


def _build_verbose_json_response(
    task: TaskEnum,
    transcript: dict[str, Any],
    duration: float,
    aligned_transcription: dict[str, Any] | None,
    include_words: bool,
    requested_language: str,
) -> OpenAIVerboseJsonResponse:
    """Build the verbose JSON response payload."""
    segments = (
        aligned_transcription["segments"]
        if aligned_transcription is not None
        else transcript.get("segments", [])
    )
    words = None
    if include_words and aligned_transcription is not None:
        words = aligned_transcription.get("word_segments")

    return OpenAIVerboseJsonResponse(
        task=task.value,
        language=cast(str | None, transcript.get("language")) or requested_language,
        duration=duration,
        text=_build_text_from_transcript(transcript),
        segments=cast(list[dict[str, Any]], segments),
        words=cast(list[dict[str, Any]] | None, words),
    )


def _run_sync_transcription(
    file: StarletteUploadFile,
    openai_request: OpenAITranscriptionRequest,
    task: TaskEnum,
    file_service: FileService,
    transcription_service: ITranscriptionService,
    alignment_service: IAlignmentService,
) -> tuple[dict[str, Any], OpenAIVerboseJsonResponse]:
    """Run the transcription pipeline synchronously."""
    settings = get_settings()
    model_params, asr_options = map_request_to_whisper_params(
        openai_request=openai_request,
        task=task,
        settings=settings,
    )
    vad_options = VADOptions(vad_onset=0.5, vad_offset=0.363)

    if (
        task == TaskEnum.TRANSLATE
        and TimestampGranularity.word in openai_request.timestamp_granularities
    ):
        _raise_openai_validation_error(
            "Word timestamps are not supported for translation responses.",
            field="timestamp_granularities[]",
        )

    filename = file.filename
    if filename is None:
        raise FileValidationError(filename="unknown", reason="Filename is missing")

    _validate_file_extension_or_raise_openai(file_service, filename)
    temp_file = _save_upload_or_raise_openai(file_service, file)

    gpu_semaphore = get_gpu_semaphore() if model_params.device.value == "cuda" else None
    semaphore_acquired = False

    try:
        audio = process_audio_file(temp_file)
        duration = get_audio_duration(audio)

        if gpu_semaphore is not None:
            logger.info("OpenAI-compatible request waiting for GPU slot")
            gpu_semaphore.acquire()
            semaphore_acquired = True

        transcript = transcription_service.transcribe(
            audio=audio,
            task=model_params.task.value,
            asr_options=asr_options.model_dump(),
            vad_options=vad_options.model_dump(),
            language=model_params.language,
            batch_size=model_params.batch_size,
            chunk_size=model_params.chunk_size,
            model=model_params.model.value,
            device=model_params.device.value,
            device_index=model_params.device_index,
            compute_type=model_params.compute_type.value,
            threads=model_params.threads,
        )

        aligned_transcription: dict[str, Any] | None = None
        if TimestampGranularity.word in openai_request.timestamp_granularities:
            aligned_payload = alignment_service.align(
                transcript=cast(list[dict[str, Any]], transcript.get("segments", [])),
                audio=audio,
                language_code=cast(str | None, transcript.get("language"))
                or model_params.language,
                device=model_params.device.value,
            )
            aligned_transcription = filter_aligned_transcription(
                AlignedTranscription(**aligned_payload)
            ).model_dump()

        return transcript, _build_verbose_json_response(
            task=task,
            transcript=transcript,
            duration=duration,
            aligned_transcription=aligned_transcription,
            include_words=TimestampGranularity.word
            in openai_request.timestamp_granularities,
            requested_language=model_params.language,
        )
    finally:
        if gpu_semaphore is not None and semaphore_acquired:
            gpu_semaphore.release()
            logger.info("GPU slot released for OpenAI-compatible request")
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def _build_openai_response(
    openai_request: OpenAITranscriptionRequest,
    verbose_response: OpenAIVerboseJsonResponse,
) -> Response:
    """Render the requested OpenAI-compatible response format."""
    text = verbose_response.text
    segments = verbose_response.segments

    if openai_request.response_format == OpenAIResponseFormat.text:
        return PlainTextResponse(content=text, media_type="text/plain")

    if openai_request.response_format == OpenAIResponseFormat.srt:
        return PlainTextResponse(
            content=_render_segments_as_subtitles(segments, OpenAIResponseFormat.srt),
            media_type="application/x-subrip",
        )

    if openai_request.response_format == OpenAIResponseFormat.vtt:
        return PlainTextResponse(
            content=_render_segments_as_subtitles(segments, OpenAIResponseFormat.vtt),
            media_type="text/vtt",
        )

    if openai_request.response_format == OpenAIResponseFormat.verbose_json:
        return JSONResponse(content=verbose_response.model_dump())

    return JSONResponse(
        content=OpenAIJsonTranscriptionResponse(text=text).model_dump(),
    )


def _build_openai_task(
    openai_request: OpenAITranscriptionRequest,
    task: TaskEnum,
    filename: str | None,
    start_time: datetime,
) -> DomainTask:
    """Build a domain Task entity for a synchronous OpenAI-compatible request."""
    return DomainTask(
        uuid=str(uuid4()),
        status=TaskStatus.processing,
        task_type=TaskType.transcription,
        file_name=filename,
        language=openai_request.language,
        task_params={
            "model": openai_request.model,
            "task": task.value,
            "response_format": openai_request.response_format.value,
            "temperature": openai_request.temperature,
            "timestamp_granularities": [
                granularity.value
                for granularity in openai_request.timestamp_granularities
            ],
            "prompt": openai_request.prompt,
        },
        start_time=start_time,
    )


async def _handle_openai_transcription(
    request: Request,
    task: TaskEnum,
    file_service: FileService,
    transcription_service: ITranscriptionService,
    alignment_service: IAlignmentService,
    repository: ITaskRepository,
) -> Response:
    """Handle a synchronous OpenAI-compatible transcription request."""
    openai_request, file = await _parse_openai_transcription_request(request)

    start_time = datetime.now(tz=timezone.utc)
    identifier = await repository.add(
        _build_openai_task(openai_request, task, file.filename, start_time)
    )

    try:
        _transcript, verbose_response = await run_in_threadpool(
            _run_sync_transcription,
            file,
            openai_request,
            task,
            file_service,
            transcription_service,
            alignment_service,
        )
    except Exception as exc:
        await repository.update(
            identifier,
            {
                "status": TaskStatus.failed,
                "error": str(exc),
                "end_time": datetime.now(tz=timezone.utc),
            },
        )
        raise

    end_time = datetime.now(tz=timezone.utc)
    await repository.update(
        identifier,
        {
            "status": TaskStatus.completed,
            "result": verbose_response.model_dump(),
            "audio_duration": verbose_response.duration,
            "language": verbose_response.language,
            "duration": (end_time - start_time).total_seconds(),
            "end_time": end_time,
        },
    )
    return _build_openai_response(openai_request, verbose_response)


@openai_compat_router.post(
    "/audio/transcriptions",
    status_code=status.HTTP_200_OK,
    summary="Transcribe audio synchronously with an OpenAI-compatible API",
    responses=_OPENAI_NON_JSON_RESPONSES,
)
async def create_transcription(
    request: Request,
    file_service: Annotated[FileService, Depends(get_file_service)],
    transcription_service: Annotated[
        ITranscriptionService, Depends(get_transcription_service)
    ],
    alignment_service: Annotated[IAlignmentService, Depends(get_alignment_service)],
    repository: Annotated[ITaskRepository, Depends(get_task_repository)],
    _authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> Response:
    """Transcribe an uploaded file and return the transcript synchronously.

    The transcript is returned directly in the response. The request is also
    persisted as a task, so its result (or error) can be retrieved afterwards via
    the `/task/{identifier}` and `/task/all` endpoints.
    """
    return await _handle_openai_transcription(
        request=request,
        task=TaskEnum.TRANSCRIBE,
        file_service=file_service,
        transcription_service=transcription_service,
        alignment_service=alignment_service,
        repository=repository,
    )


@openai_compat_router.post(
    "/audio/translations",
    status_code=status.HTTP_200_OK,
    summary="Translate audio to English synchronously with an OpenAI-compatible API",
    responses=_OPENAI_NON_JSON_RESPONSES,
)
async def create_translation(
    request: Request,
    file_service: Annotated[FileService, Depends(get_file_service)],
    transcription_service: Annotated[
        ITranscriptionService, Depends(get_transcription_service)
    ],
    alignment_service: Annotated[IAlignmentService, Depends(get_alignment_service)],
    repository: Annotated[ITaskRepository, Depends(get_task_repository)],
    _authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> Response:
    """Translate an uploaded file to English and return the result synchronously.

    The translation is returned directly in the response. The request is also
    persisted as a task, so its result (or error) can be retrieved afterwards via
    the `/task/{identifier}` and `/task/all` endpoints.
    """
    return await _handle_openai_transcription(
        request=request,
        task=TaskEnum.TRANSLATE,
        file_service=file_service,
        transcription_service=transcription_service,
        alignment_service=alignment_service,
        repository=repository,
    )
