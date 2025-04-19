# whisperX REST API

The whisperX API is a tool for enhancing and analyzing audio content. This API provides a suite of services for processing audio and video files, including transcription, alignment, diarization, and combining transcript with diarization results.

## Documentation

Swagger UI is available at `/docs` for all the services, dump of OpenAPI definition is available in folder `app/docs` as well. You can explore it directly in [Swagger Editor](https://editor.swagger.io/?url=https://raw.githubusercontent.com/pavelzbornik/whisperX-FastAPI/main/app/docs/openapi.yaml)

See the [WhisperX Documentation](https://github.com/m-bain/whisperX) for details on whisperX functions.

### Language and Whisper model settings

- in `.env` you can define default Language `DEFAULT_LANG`, if not defined **en** is used (you can also set it in the request)
- `.env` contains definition of Whisper model using `WHISPER_MODEL` (you can also set it in the request)
- `.env` contains definition of logging level using `LOG_LEVEL`, if not defined **DEBUG** is used in development and **INFO** in production
- `.env` contains definition of environment using `ENVIRONMENT`, if not defined **production** is used
- `.env` contains a boolean `DEV` to indicate if the environment is development, if not defined **true** is used
- `.env` contains a boolean `FILTER_WARNING` to enable or disable filtering of specific warnings, if not defined **true** is used

### Supported File Formats

#### Audio Files

- `.oga`, `.m4a`, `.aac`, `.wav`, `.amr`, `.wma`, `.awb`, `.mp3`, `.ogg`

#### Video Files

- `.wmv`, `.mkv`, `.avi`, `.mov`, `.mp4`

### Available Services

1. Speech-to-Text (`/speech-to-text`)

   - Upload audio/video files for transcription
   - Supports multiple languages and Whisper models

2. Speech-to-Text URL (`/speech-to-text-url`)

   - Transcribe audio/video from URLs
   - Same features as direct upload

3. Individual Services:

   - Transcribe (`/service/transcribe`): Convert speech to text
   - Align (`/service/align`): Align transcript with audio
   - Diarize (`/service/diarize`): Speaker diarization
   - Combine (`/service/combine`): Merge transcript with diarization

4. Task Management:

   - Get all tasks (`/task/all`)
   - Get task status (`/task/{identifier}`)

5. Health Check Endpoints:
   - Basic health check (`/health`): Simple service status check
   - Liveness probe (`/health/live`): Verifies if application is running
   - Readiness probe (`/health/ready`): Checks if application is ready to accept requests (includes database connectivity check)

### Task management and result storage

![Service chart](app/docs/service_chart.svg)

Status and result of each tasks are stored in db using ORM Sqlalchemy, db connection is defined by environment variable `DB_URL` if value is not specified `db.py` sets default db as `sqlite:///records.db`

See documentation for driver definition at [Sqlalchemy Engine configuration](https://docs.sqlalchemy.org/en/20/core/engines.html) if you want to connect other type of db than Sqlite.

#### Database schema

Structure of the of the db is described in [DB Schema](app/docs/db_schema.md)

### Compute Settings

Configure compute options in `.env`:

- `DEVICE`: Device for inference (`cuda` or `cpu`, default: `cuda`)
- `COMPUTE_TYPE`: Computation type (`float16`, `float32`, `int8`, default: `float16`)
  > Note: When using CPU, `COMPUTE_TYPE` must be set to `int8`

### Available Models

WhisperX supports these model sizes:

- `tiny`, `tiny.en`
- `base`, `base.en`
- `small`, `small.en`
- `medium`, `medium.en`
- `large`, `large-v1`, `large-v2`, `large-v3`, `large-v3-turbo`
- Distilled models: `distil-large-v2`, `distil-medium.en`, `distil-small.en`, `distil-large-v3`
- Custom models: [`nyrahealth/faster_CrisperWhisper`](https://github.com/nyrahealth/CrisperWhisper)

Set default model in `.env` using `WHISPER_MODEL=` (default: tiny)

## System Requirements

- NVIDIA GPU with CUDA 12.8+ support
- At least 8GB RAM (16GB+ recommended for large models)
- Storage space for models (varies by model size):
  - tiny/base: ~1GB
  - small: ~2GB
  - medium: ~5GB
  - large: ~10GB

## Getting Started

### Local Run

To get started with the API, follow these steps:

1. Create virtual environment
2. Install pytorch [See for more details](https://pytorch.org/)
3. Install the required dependencies (choose one):

   ```sh
   # For production dependencies only
   pip install -r requirements/prod.txt

   # For development dependencies (includes production + testing, linting, etc.)
   pip install -r requirements/dev.txt
   ```

> **Note:** The above steps use `pip` for local development. For Docker builds, package management is handled by [`uv`](https://github.com/astral-sh/uv) as specified in the [dockerfile](dockerfile) for improved performance and reliability.

### Logging Configuration

The application uses two logging configuration files:

- `uvicorn_log_conf.yaml`: Used by Uvicorn for logging configuration.
- `gunicorn_logging.conf`: Used by Gunicorn for logging configuration (located in the root of the `app` directory).

Ensure these files are correctly configured and placed in the `app` directory.

5. Create `.env` file

define your Whisper Model and token for Huggingface

```sh
HF_TOKEN=<<YOUR HUGGINGFACE TOKEN>>
WHISPER_MODEL=<<WHISPER MODEL SIZE>>
LOG_LEVEL=<<LOG LEVEL>>
```

6. Run the FastAPI application:

```sh
uvicorn app.main:app --reload --log-config uvicorn_log_conf.yaml --log-level $LOG_LEVEL
```

The API will be accessible at <http://127.0.0.1:8000>.

### Docker Build

1. Create `.env` file

define your Whisper Model and token for Huggingface

```sh
HF_TOKEN=<<YOUR HUGGINGFACE TOKEN>>
WHISPER_MODEL=<<WHISPER MODEL SIZE>>
LOG_LEVEL=<<LOG LEVEL>>
```

2. Build Image

using `docker-compose.yaml`

```sh
#build and start the image using compose file
docker-compose up
```

alternative approach

```sh
#build image
docker build -t whisperx-service .

# Run Container
docker run -d --gpus all -p 8000:8000 --env-file .env whisperx-service
```

The API will be accessible at <http://127.0.0.1:8000>.

> **Note:** The Docker build uses `uv` for installing dependencies, as specified in the Dockerfile.
> The main entrypoint for the Docker container is via **Gunicorn** (not Uvicorn directly), using the configuration in `app/gunicorn_logging.conf`.
>
> **Important:** For GPU support in Docker, you must have **CUDA drivers 12.8+ installed on your host system**.

#### Model cache

The models used by whisperX are stored in `root/.cache`, if you want to avoid downloanding the models each time the container is starting you can store the cache in persistent storage. `docker-compose.yaml` defines a volume `whisperx-models-cache` to store this cache.

- faster-whisper cache: `root/.cache/huggingface/hub`
- pyannotate and other models cache: `root/.cache/torch`

## Troubleshooting

### Common Issues

1. **Environment Variables Not Loaded**

   - Ensure your `.env` file is correctly formatted and placed in the root directory.
   - Verify that all required environment variables are defined.

2. **Database Connection Issues**

   - Check the `DB_URL` environment variable for correctness.
   - Ensure the database server is running and accessible.

3. **Model Download Failures**

   - Verify your internet connection.
   - Ensure the `HF_TOKEN` is correctly set in the `.env` file.

4. **GPU Not Detected**

   - Ensure NVIDIA drivers and CUDA are correctly installed.
   - Verify that Docker is configured to use the GPU (`nvidia-docker`).

5. **Warnings Not Filtered**
   - Ensure the `FILTER_WARNING` environment variable is set to `true` in the `.env` file.

### Logs and Debugging

- Check the logs for detailed error messages.
- Use the `LOG_LEVEL` environment variable to set the appropriate logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

### Monitoring and Health Checks

The API provides built-in health check endpoints that can be used for monitoring and orchestration:

1. **Basic Health Check** (`/health`)

   - Returns a simple status check with HTTP 200 if the service is running
   - Useful for basic availability monitoring

2. **Liveness Probe** (`/health/live`)

   - Includes a timestamp with status information
   - Designed for Kubernetes liveness probes or similar orchestration systems
   - Returns HTTP 200 if the application is running

3. **Readiness Probe** (`/health/ready`)
   - Tests if the application is fully ready to accept requests
   - Checks connectivity to the database
   - Returns HTTP 200 if all dependencies are available
   - Returns HTTP 503 if there's an issue with dependencies (e.g., database connection)

### Support

For further assistance, please open an issue on the [GitHub repository](https://github.com/pavelzbornik/whisperX-FastAPI/issues).

## Related

- [ahmetoner/whisper-asr-webservice](https://github.com/ahmetoner/whisper-asr-webservice)
- [alexgo84/whisperx-server](https://github.com/alexgo84/whisperx-server)
- [chinaboard/whisperX-service](https://github.com/chinaboard/whisperX-service)
- [tijszwinkels/whisperX-api](https://github.com/tijszwinkels/whisperX-api)
