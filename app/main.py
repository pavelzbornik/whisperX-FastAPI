from fastapi import (
    FastAPI,
    File,
    UploadFile,
    Form,
    HTTPException,
    Depends,
)
from fastapi.responses import RedirectResponse
from fastapi import BackgroundTasks
import whisperx

from .models import (
    Response,
    Result,
    ResultTasks,
    Transcript,
    AlignedTranscription,
    DiarizationSegment,
    Base,
)

from pydantic import ValidationError

import pandas as pd

import json

from sqlalchemy.orm import Session

from .services import (
    # generate_unique_identifier,
    # update_transcription_status,
    process_audio_common,
    download_and_process_file,
    process_transcribe,
    process_diarize,
    process_audio_file,
    process_alignment,
    process_speaker_assignment,
    validate_language_code,
)

from .files import (
    save_temporary_file,
    validate_extension,
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    ALLOWED_EXTENSIONS,
)

from .tasks import (
    get_task_status_from_db,
    get_all_tasks_status_from_db,
    add_task_to_db,
)

from .db import (
    get_db_session,
    engine,
)

Base.metadata.create_all(bind=engine)

tags_metadata = [
    {
        "name": "Speech-2-Text",
        "description": "Operations related to transcript",
    },
    {
        "name": "Speech-2-Text services",
        "description": "Individual services for transcript",
    },
    {
        "name": "Tasks Management",
        "description": "Manage tasks.",
    },
]


app = FastAPI(
    title="whisperX REST service",
    description=f"""
# whisperX REST Service

Welcome to the whisperX RESTful API! This API provides a suite of audio processing services to enhance and analyze your audio content.

## Documentation:

For detailed information on request and response formats, consult the [WhisperX Documentation](https://github.com/m-bain/whisperX).

## Services:

Speech-2-Text provides a suite of audio processing services to enhance and analyze your audio content. The following services are available:

1. Transcribe: Transcribe an audio/video  file into text.
2. Align: Align the transcript to the audio/video file.
3. Diarize: Diarize an audio/video file into speakers.
4. Combine Transcript and Diarization: Combine the transcript and diarization results.

## Supported file extensions:
AUDIO_EXTENSIONS = {AUDIO_EXTENSIONS}

VIDEO_EXTENSIONS = {VIDEO_EXTENSIONS}

""",
    version="0.0.1",
    openapi_tags=tags_metadata,
)


@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def index():
    """
    Redirect to the documentation.

    """
    return "/docs"


@app.post("/speech-to-text", tags=["Speech-2-Text"])
async def speech_to_text(
    background_tasks: BackgroundTasks,
    language: str = None,
    file: UploadFile = File(
        ...,
        title="Audio/Video File",
        description="File to be processed",
        example="audio_file.mp3",
    ),
    session: Session = Depends(get_db_session),
) -> Response:
    """
    Process an audio/video file in the background in full process.

    Args:
        background_tasks (BackgroundTasks): The BackgroundTasks object.
        audio_file (UploadFile): The audio file to process.

    Returns:
        dict: A dictionary containing the identifier and a message. The message is "Task queued". The identifier is a unique identifier for the transcription request.
    """
    # Generate a unique identifier for the transcription request
    # identifier = generate_unique_identifier()

    validate_extension(file.filename, ALLOWED_EXTENSIONS)
    if language:
        validate_language_code(language)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = process_audio_file(temp_file)

    # Save the identifier and set the initial status to "processing" in the database
    identifier = add_task_to_db(
        # identifier=identifier,
        status="processing",
        file_name=file.filename,
        task_type="full_process",
        session=session,
    )

    # Save the identifier and set the initial status to "processing"
    # update_transcription_status(
    #     identifier=identifier,
    #     status="processing",
    #     file_name=file.filename,
    #     task_type="full_process",
    # )

    # Use background tasks to perform the audio processing
    background_tasks.add_task(
        process_audio_common,
        audio,
        identifier,
        session,
        language,
    )

    # Return the identifier to the user
    return Response(identifier=identifier, message="Task queued")


@app.post("/transcribe", tags=["Speech-2-Text services"], name="1. Transcribe")
async def transcribe(
    background_tasks: BackgroundTasks,
    language: str = None,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> Response:
    # identifier = generate_unique_identifier()

    validate_extension(file.filename, ALLOWED_EXTENSIONS)
    if language:
        validate_language_code(language)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = whisperx.load_audio(temp_file)

    # update_transcription_status(
    #     identifier,
    #     "processing",
    #     file_name=file.filename,
    #     task_type="transcription",
    # )
    identifier = add_task_to_db(
        # identifier=identifier,
        status="processing",
        file_name=file.filename,
        task_type="transcription",
        session=session,
    )

    background_tasks.add_task(
        process_transcribe,
        audio,
        identifier,
        language,
        session,
    )

    return Response(identifier=identifier, message="Task queued")


@app.post(
    "/align", tags=["Speech-2-Text services"], name="2. Align Transcript"
)
def align(
    background_tasks: BackgroundTasks,
    transcript: UploadFile = File(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
):
    validate_extension(transcript.filename, {".json"})

    try:
        # Read the content of the transcript file
        transcript = Transcript(**json.loads(transcript.file.read()))
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON content. {str(e)}"
        )

    # identifier = generate_unique_identifier()

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = whisperx.load_audio(temp_file)

    identifier = add_task_to_db(
        # identifier=identifier,
        status="processing",
        file_name=file.filename,
        task_type="transcription_aligment",
        session=session,
    )
    # update_transcription_status(
    #     identifier,
    #     "processing",
    #     file_name=file.filename,
    #     task_type="transcription_aligment",
    # )

    background_tasks.add_task(
        process_alignment,
        audio,
        transcript.model_dump(),
        identifier,
        session,
    )

    return Response(identifier=identifier, message="Task queued")


@app.post("/diarize", tags=["Speech-2-Text services"], name="3. Diarize")
async def diarize(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> Response:
    # identifier = generate_unique_identifier()

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = whisperx.load_audio(temp_file)

    # update_transcription_status(
    #     identifier,
    #     "processing",
    #     file_name=file.filename,
    #     task_type="diarization",
    # )
    identifier = add_task_to_db(
        # identifier=identifier,
        status="processing",
        file_name=file.filename,
        task_type="diarization",
        session=session,
    )
    background_tasks.add_task(process_diarize, audio, identifier, session)

    return Response(identifier=identifier, message="Task queued")


@app.post(
    "/combine",
    tags=["Speech-2-Text services"],
    name="4. Combine Transcript and Diarization result",
)
async def combine(
    background_tasks: BackgroundTasks,
    aligned_transcript: UploadFile = File(...),
    diarization_result: UploadFile = File(...),
    session: Session = Depends(get_db_session),
):
    # identifier = generate_unique_identifier()

    validate_extension(aligned_transcript.filename, {".json"})
    validate_extension(diarization_result.filename, {".json"})

    try:
        # Read the content of the transcript file
        transcript = AlignedTranscription(
            **json.loads(aligned_transcript.file.read())
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON content. {str(e)}"
        )
    try:
        # Map JSON to list of models
        diarization_segments = []
        for item in json.loads(diarization_result.file.read()):
            diarization_segments.append(DiarizationSegment(**item))
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON content. {str(e)}"
        )

    # update_transcription_status(
    #     identifier,
    #     "processing",
    #     file_name=None,
    #     task_type="combine_transcript&diarization",
    # )
    identifier = add_task_to_db(
        # identifier=identifier,
        status="processing",
        file_name=None,
        task_type="combine_transcript&diarization",
        session=session,
    )
    background_tasks.add_task(
        process_speaker_assignment,
        pd.json_normalize(
            [segment.model_dump() for segment in diarization_segments]
        ),
        transcript.model_dump(),
        identifier,
        session,
    )

    return Response(identifier=identifier, message="Task queued")


@app.post("/speech-to-text-url", tags=["Speech-2-Text"])
async def speech_to_text_url(
    background_tasks: BackgroundTasks,
    language: str = None,
    url: str = Form(...),
    session: Session = Depends(get_db_session),
) -> Response:
    return download_and_process_file(url, background_tasks, session, language)


@app.get("/transcription_status/{uuid}", tags=["Tasks Management"])
async def get_transcription_status(
    uuid: str,
    session: Session = Depends(get_db_session),
) -> Result:
    # Check if the identifier exists in the transcription_requests dictionary

    status = get_task_status_from_db(uuid, session)

    if status is not None:
        # If the identifier is found, return the status
        return status
    else:
        # If the identifier is not found, return a 404 response
        raise HTTPException(status_code=404, detail="Identifier not found")


@app.get("/all_tasks_status", tags=["Tasks Management"])
async def get_all_tasks_status(
    session: Session = Depends(get_db_session),
) -> ResultTasks:
    return get_all_tasks_status_from_db(session)
