# ML Service Abstraction Pattern

## Overview

This document describes the ML service abstraction layer implemented in the whisperX-FastAPI application. The abstraction decouples the application from specific ML libraries (WhisperX), making it easier to test, maintain, and extend with alternative ML providers.

## Architecture Pattern

The application follows **Dependency Inversion Principle** using **Protocol-based interfaces**:

```text
┌─────────────────────────────────────┐
│        API Layer (Routers)          │
│   - audio_api.py                    │
│   - audio_services_api.py           │
└──────────────┬──────────────────────┘
               │ Depends()
               ↓
┌─────────────────────────────────────┐
│    Domain Services (Interfaces)     │
│   - ITranscriptionService           │
│   - IDiarizationService             │
│   - IAlignmentService               │
│   - ISpeakerAssignmentService       │
└──────────────┬──────────────────────┘
               ↑ implements
┌──────────────┴──────────────────────┐
│  Infrastructure Layer (WhisperX)    │
│   - WhisperXTranscriptionService    │
│   - WhisperXDiarizationService      │
│   - WhisperXAlignmentService        │
│   - WhisperXSpeakerAssignmentService│
└─────────────────────────────────────┘
```

## Key Components

### 1. Domain Service Interfaces

Located in `app/domain/services/`, these Protocol-based interfaces define contracts for ML operations without implementation details.

#### ITranscriptionService

```python
class ITranscriptionService(Protocol):
    """Interface for audio transcription services."""

    def transcribe(
        self, audio, task, asr_options, vad_options,
        language, batch_size, chunk_size, model,
        device, device_index, compute_type, threads
    ) -> dict[str, Any]:
        """Transcribe audio to text with segments."""
        ...

    def load_model(...) -> None:
        """Load ML model for transcription."""
        ...

    def unload_model() -> None:
        """Unload ML model to free resources."""
        ...
```

**Benefits:**

- Protocol-based typing (structural subtyping)
- No runtime overhead
- IDE autocomplete support
- Type-safe interface contract

#### Other Interfaces

- **IDiarizationService**: Speaker diarization operations
- **IAlignmentService**: Transcript-to-audio alignment
- **ISpeakerAssignmentService**: Speaker label assignment

### 2. Infrastructure Implementations

Located in `app/infrastructure/ml/`, these classes implement the interfaces using WhisperX.

**Example - WhisperXTranscriptionService:**

```python
class WhisperXTranscriptionService:
    """WhisperX-based implementation of transcription service."""

    def transcribe(self, audio, ...) -> dict[str, Any]:
        # Load WhisperX model
        loaded_model = load_model(...)

        # Transcribe
        result = loaded_model.transcribe(...)

        # Cleanup GPU memory
        gc.collect()
        torch.cuda.empty_cache()
        del loaded_model

        return result
```

**Key Features:**

- Encapsulates WhisperX-specific logic
- Handles GPU memory management
- Implements complete interface contract
- Logging for all operations

### 3. Dependency Injection

Located in `app/api/dependencies.py`:

```python
def get_transcription_service() -> ITranscriptionService:
    """Provide transcription service for DI."""
    return WhisperXTranscriptionService()

def get_diarization_service() -> IDiarizationService:
    """Provide diarization service for DI."""
    hf_token = Config.HF_TOKEN or ""
    return WhisperXDiarizationService(hf_token=hf_token)
```

**Benefits:**

- Single source of truth for service instantiation
- Easy to override for testing
- Centralized configuration

### 4. API Integration

Routers inject services via FastAPI's dependency injection:

```python
@router.post("/service/transcribe")
async def transcribe(
    background_tasks: BackgroundTasks,
    model_params: WhisperModelParams = Depends(),
    transcription_service: ITranscriptionService = Depends(get_transcription_service),
    # ... other params
) -> Response:
    # Use service interface
    background_tasks.add_task(
        process_transcribe,
        audio, identifier, model_params,
        asr_options, vad_options,
        transcription_service  # Injected service
    )
    return Response(identifier=identifier, message="Task queued")
```

## Testing with Mocks

### Mock Services

Located in `tests/mocks/`, mock services provide fast unit testing without ML overhead.

**Example - MockTranscriptionService:**

```python
class MockTranscriptionService:
    """Mock transcription service for testing."""

    def __init__(self, mock_result=None, should_fail=False):
        self.mock_result = mock_result or self._default_result()
        self.should_fail = should_fail
        self.transcribe_called = False
        self.transcribe_call_count = 0

    def transcribe(self, audio, ...) -> dict[str, Any]:
        """Return mock result immediately."""
        self.transcribe_called = True
        self.transcribe_call_count += 1

        if self.should_fail:
            raise RuntimeError("Mock transcription failed")

        return self.mock_result

    def _default_result(self) -> dict[str, Any]:
        return {
            "text": "This is a test transcription.",
            "segments": [...],
            "language": "en"
        }
```

### Using Mocks in Tests

```python
def test_audio_processing_with_mock():
    # Create mock services
    mock_transcription = MockTranscriptionService()
    mock_diarization = MockDiarizationService()
    mock_alignment = MockAlignmentService()
    mock_speaker = MockSpeakerAssignmentService()

    # Override dependency injection
    app.dependency_overrides[get_transcription_service] = lambda: mock_transcription
    app.dependency_overrides[get_diarization_service] = lambda: mock_diarization

    # Test business logic without ML overhead
    response = client.post("/service/transcribe", ...)

    # Verify service was called
    assert mock_transcription.transcribe_called
    assert response.status_code == 200
```

**Benefits:**

- Tests run in milliseconds instead of minutes
- No GPU required for unit tests
- Test business logic in isolation
- Easy to test error conditions

## Adding Alternative ML Providers

The abstraction makes it trivial to add new ML providers:

### Example: OpenAI Whisper API

```python
# app/infrastructure/ml/openai_transcription_service.py
import openai

class OpenAITranscriptionService:
    """OpenAI API-based transcription service."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        openai.api_key = api_key

    def transcribe(self, audio, ...) -> dict[str, Any]:
        """Transcribe using OpenAI API."""
        # Convert parameters to OpenAI format
        with open(temp_audio_file, 'wb') as f:
            f.write(audio.tobytes())

        # Call OpenAI API
        response = openai.Audio.transcribe(
            "whisper-1",
            temp_audio_file,
            language=language
        )

        # Convert to standard format
        return {
            "text": response["text"],
            "segments": self._parse_segments(response),
            "language": language
        }
```

### Switch Providers via Configuration

```python
# app/api/dependencies.py
def get_transcription_service() -> ITranscriptionService:
    """Provide transcription service based on configuration."""
    provider = Config.ML_PROVIDER  # "whisperx" or "openai"

    if provider == "openai":
        return OpenAITranscriptionService(api_key=Config.OPENAI_API_KEY)
    else:
        return WhisperXTranscriptionService()
```

**No changes required in:**

- API routers
- Service layer
- Domain logic
- Tests (except integration tests)

### Import Restrictions

To maintain clean architecture boundaries:

#### Allowed WhisperX Imports

```text
app/infrastructure/ml/              ← WhisperX implementations
app/services/whisperx_wrapper_service.py  ← Legacy wrapper (transitional)
app/schemas.py                      ← Validation utilities
app/audio.py                        ← Audio processing utilities
```

#### Prohibited WhisperX Imports

```text
app/domain/                         ← Pure domain logic
app/services/ (except wrapper)      ← Service layer
app/api/                            ← API layer
```

### Verification

```bash
# Check for violations
grep -r "^import whisperx\|^from whisperx" app/ \
  --include="*.py" \
  --exclude-dir="infrastructure/ml" \
  | grep -v "whisperx_wrapper_service.py" \
  | grep -v "schemas.py" \
  | grep -v "audio.py"

# Should return empty (no violations)
```

## Benefits Summary

### For Development

1. **Testability**: Fast unit tests with mocks
2. **Maintainability**: Clear separation of concerns
3. **Type Safety**: Full mypy support with Protocols
4. **Flexibility**: Easy to swap ML providers
5. **Debugging**: Clear boundaries for troubleshooting

### For Production

1. **Performance**: No abstraction overhead
2. **Reliability**: Same WhisperX implementation
3. **Monitoring**: Centralized logging in services
4. **Deployment**: No changes to existing functionality

### For Future

1. **Multi-Provider**: Support multiple ML backends
2. **A/B Testing**: Compare ML provider performance
3. **Cost Optimization**: Switch to cheaper providers
4. **Feature Flags**: Toggle providers per user/environment

## Migration Path

The existing `whisperx_wrapper_service.py` has been updated to:

1. Accept optional service parameters
2. Default to WhisperX implementations if None provided
3. Maintain backward compatibility

This allows gradual migration:

1. ✅ Interfaces defined
2. ✅ WhisperX implementations created
3. ✅ Dependency injection configured
4. ✅ New endpoints use DI
5. ⏳ Legacy endpoints migrated incrementally
6. ⏳ Old wrapper deprecated and removed

## Testing Checklist

### Unit Tests (with Mocks)

- [ ] Test API endpoint validation
- [ ] Test error handling
- [ ] Test task creation and updates
- [ ] Test file uploads and downloads
- [ ] Test business logic flows

#### Execution Time

Less than 1 second

### Integration Tests (with Real WhisperX)

- [ ] Test actual transcription accuracy
- [ ] Test diarization quality
- [ ] Test alignment precision
- [ ] Test GPU memory management
- [ ] Test end-to-end workflows

#### Expected Duration

Approximately 30 seconds per test

## Conclusion

The ML service abstraction provides a clean, maintainable, and testable architecture while preserving the existing WhisperX functionality. It follows SOLID principles and enables future extensibility without breaking changes.
