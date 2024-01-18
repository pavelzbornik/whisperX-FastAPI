# whisperX REST API

The whisperX API is a tool for enhancing and analyzing audio content. This API provides a suite of services for processing audio and video files, including transcription, alignment, diarization, and combining transcript with diarization results.

## Documentation

Swagger UI is available at `/docs` for all the services

See the [WhisperX Documentation](https://github.com/m-bain/whisperX) for details on whisperX functions.

## Services

The following services are available:

1. Transcribe - Transcribe an audio/video file into text.
2. Align - Align the transcript to the audio/video file. 
3. Diarize - Diarize an audio/video file with speakers.
4. Combine Transcript and Diarization - Combine the transcript and diarization results.


## Usage

Make POST requests to the following endpoints:

- **/speech-to-text** - Process an audio/video file.
- **/speech-to-text-url** - Download and process an audio/video file.

Individual services
- **/transcribe** - Transcribe an audio file. 
- **/align** - Align a transcript to an audio file.
- **/diarize** - Diarize an audio file into speakers.
- **/combine** - Combine transcript and diarization results.

## Status

Get the status of a job via GET /transcription_status/{identifier}

## Language and Whisper model settings

In `services.py` you can define:

- default Language constant `LANG = "en"` (you can also set it in the request)


## Getting Started

### Local Run

To get started with the API, follow these steps:

1. Create virtual enviroment
2. Install pytorch [See for more details](https://pytorch.org/)
3. Install whisperX

```
pip install git+https://github.com/m-bain/whisperx.git
```
4. Install the required dependencies:
```
pip install -r requirements.txt
```
5. Create `.env` file

define your Whisper Model and token for Huggingface
```
HF_TOKEN=<<YOUR HUGGINGFACE TOKEN>>
WHISPER_MODEL=<<WHISPER MODEL SIZE>>
```

6. Run the FastAPI application:

```
uvicorn app.main:app --reload
```
The API will be accessible at http://127.0.0.1:8000.

### Docker Build

1. Create `.env` file

```
HF_TOKEN=<<YOUR HUGGINGFACE TOKEN>>
WHISPER_MODEL=<<WHISPER MODEL SIZE>>
```

2. Build Image

```sh
#build image
docker build -t whisperx-service .

# Run Container
docker run -d --gpus all -p 8000:8000 whisperx-service
```
The API will be accessible at http://127.0.0.1:8000.

## Related
- [ahmetoner/whisper-asr-webservice](https://github.com/ahmetoner/whisper-asr-webservice)
- [alexgo84/whisperx-server](https://github.com/alexgo84/whisperx-server)
- [chinaboard/whisperX-service](https://github.com/chinaboard/whisperX-service)
- [tijszwinkels/whisperX-api](https://github.com/tijszwinkels/whisperX-api)