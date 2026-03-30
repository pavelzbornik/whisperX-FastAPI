"""Speaker embedding API endpoints — CRUD, search, and identification."""

from fastapi import APIRouter, Depends, Query
from starlette import status
from starlette.responses import JSONResponse

from app.api.dependencies import get_speaker_service
from app.api.mappers.speaker_mapper import SpeakerMapper
from app.api.schemas.speaker_schemas import (
    CreateSpeakerRequest,
    SpeakerIdentifyRequest,
    SpeakerResponse,
    SpeakerSearchRequest,
    SpeakerSearchResponse,
    SpeakerSearchResult,
    UpdateSpeakerRequest,
)
from app.services.speaker_service import SpeakerService

speaker_router = APIRouter()


@speaker_router.post(
    "/speakers",
    tags=["Speakers"],
    name="Create speaker",
    status_code=status.HTTP_201_CREATED,
)
async def create_speaker(
    request: CreateSpeakerRequest,
    speaker_service: SpeakerService = Depends(get_speaker_service),
) -> JSONResponse:
    """Create a new speaker embedding."""
    uuid = await speaker_service.create(
        speaker_label=request.speaker_label,
        embedding=request.embedding,
        description=request.description,
        task_uuid=request.task_uuid,
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"uuid": uuid, "message": "Speaker created"},
    )


@speaker_router.get(
    "/speakers",
    tags=["Speakers"],
    name="List speakers",
    response_model=list[SpeakerResponse],
)
async def list_speakers(
    task_id: str | None = Query(
        default=None, description="Filter by originating task UUID"
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    speaker_service: SpeakerService = Depends(get_speaker_service),
) -> list[SpeakerResponse]:
    """List speaker embeddings with optional task filter and pagination."""
    if task_id:
        all_task_speakers = await speaker_service.get_by_task(task_id)
        speakers = all_task_speakers[offset : offset + limit]
    else:
        speakers = await speaker_service.list_all(limit=limit, offset=offset)
    return [SpeakerMapper.to_response(s) for s in speakers]


@speaker_router.get(
    "/speakers/{uuid}",
    tags=["Speakers"],
    name="Get speaker",
    response_model=SpeakerResponse,
)
async def get_speaker(
    uuid: str,
    speaker_service: SpeakerService = Depends(get_speaker_service),
) -> SpeakerResponse | JSONResponse:
    """Get a single speaker embedding by UUID."""
    speaker = await speaker_service.get_by_id(uuid)
    if speaker is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Speaker {uuid} not found"},
        )
    return SpeakerMapper.to_response(speaker)


@speaker_router.put(
    "/speakers/{uuid}",
    tags=["Speakers"],
    name="Update speaker",
)
async def update_speaker(
    uuid: str,
    request: UpdateSpeakerRequest,
    speaker_service: SpeakerService = Depends(get_speaker_service),
) -> JSONResponse:
    """Update a speaker's label, description, or embedding."""
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    if not update_data:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "No fields to update"},
        )

    found = await speaker_service.update(uuid, update_data)
    if not found:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Speaker {uuid} not found"},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Speaker updated"},
    )


@speaker_router.delete(
    "/speakers/{uuid}",
    tags=["Speakers"],
    name="Delete speaker",
)
async def delete_speaker(
    uuid: str,
    speaker_service: SpeakerService = Depends(get_speaker_service),
) -> JSONResponse:
    """Delete a single speaker embedding."""
    found = await speaker_service.delete(uuid)
    if not found:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Speaker {uuid} not found"},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Speaker deleted"},
    )


@speaker_router.delete(
    "/speakers",
    tags=["Speakers"],
    name="Delete speakers by task",
)
async def delete_speakers_by_task(
    task_id: str = Query(description="Delete all speakers from this task"),
    speaker_service: SpeakerService = Depends(get_speaker_service),
) -> JSONResponse:
    """Delete all speaker embeddings associated with a task."""
    count = await speaker_service.delete_by_task(task_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": f"Deleted {count} speaker(s)"},
    )


@speaker_router.post(
    "/speakers/search",
    tags=["Speakers"],
    name="Search speakers",
    response_model=SpeakerSearchResponse,
)
async def search_speakers(
    request: SpeakerSearchRequest,
    speaker_service: SpeakerService = Depends(get_speaker_service),
) -> SpeakerSearchResponse:
    """Search for similar speakers by embedding vector (cosine similarity)."""
    matches = await speaker_service.search_similar(
        embedding=request.embedding,
        limit=request.limit,
        threshold=request.threshold,
    )
    return SpeakerSearchResponse(
        results=[
            SpeakerSearchResult(
                speaker=SpeakerMapper.to_response(speaker),
                similarity=round(score, 4),
            )
            for speaker, score in matches
        ]
    )


@speaker_router.post(
    "/speakers/identify",
    tags=["Speakers"],
    name="Identify speaker",
)
async def identify_speaker(
    request: SpeakerIdentifyRequest,
    speaker_service: SpeakerService = Depends(get_speaker_service),
) -> JSONResponse:
    """Identify the best-matching speaker above threshold."""
    result = await speaker_service.identify(
        embedding=request.embedding,
        threshold=request.threshold,
    )
    if result is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "No matching speaker found above threshold"},
        )
    speaker, similarity = result
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "speaker": SpeakerMapper.to_response(speaker).model_dump(mode="json"),
            "similarity": round(similarity, 4),
        },
    )
