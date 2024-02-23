from fastapi import (
    File,
    UploadFile,
    Form,
    Depends,
    APIRouter
)
from fastapi import BackgroundTasks

from ..schemas import (
    Response,
)

from sqlalchemy.orm import Session

from ..services import (
    process_audio_common,
    download_and_process_file,
    process_audio_file,
    validate_language_code,
)

from ..files import (
    save_temporary_file,
    validate_extension,
    ALLOWED_EXTENSIONS,
)

from ..tasks import (
    add_task_to_db,
)

from ..db import (
    get_db_session,
)

stt_router = APIRouter()


@stt_router.post("/speech-to-text", tags=["Speech-2-Text"])
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
    validate_extension(file.filename, ALLOWED_EXTENSIONS)
    if language:
        validate_language_code(language)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = process_audio_file(temp_file)

    # Save the identifier and set the initial status to "processing" in the database
    identifier = add_task_to_db(
        status="processing",
        file_name=file.filename,
        task_type="full_process",
        session=session,
    )

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


@stt_router.post("/speech-to-text-url", tags=["Speech-2-Text"])
async def speech_to_text_url(
    background_tasks: BackgroundTasks,
    language: str = None,
    url: str = Form(...),
    session: Session = Depends(get_db_session),
) -> Response:
    return download_and_process_file(url, background_tasks, session, language)
