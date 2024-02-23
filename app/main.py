from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
)
from fastapi.responses import RedirectResponse

from .models import (
    Base,
)

from .files import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
)

from .db import (
    engine,
)

from .routers import task, stt_services, stt
from dotenv import load_dotenv
import json
import yaml

# Load environment variables from .env
load_dotenv()

Base.metadata.create_all(bind=engine)


def save_openapi_json(app):
    openapi_data = app.openapi()
    # Change "openapi.json" to desired filename
    with open("app/docs/openapi.json", "w") as file:
        json.dump(openapi_data, file, indent=2)
    with open("app/docs/openapi.yaml", "w") as f:
        yaml.dump(openapi_data, f, sort_keys=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    save_openapi_json(app)
    yield


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
    lifespan=lifespan,
)

app.include_router(stt.stt_router)
app.include_router(task.task_router)
app.include_router(stt_services.service_router)


@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def index():
    """
    Redirect to the documentation.

    """
    return "/docs"
