# Configuration Migration Guide

## Overview

This project has migrated from raw environment variable parsing to **Pydantic Settings** for type-safe, validated configuration management.

## What Changed

### Before (Old Config)

```python
from app.core.config import Config

# Access configuration
model = Config.WHISPER_MODEL
db_url = Config.DB_URL
device = Config.DEVICE
```

### After (New Settings)

```python
from app.core.config import get_settings

# Access configuration
settings = get_settings()
model = settings.whisper.WHISPER_MODEL
db_url = settings.database.DB_URL
device = settings.whisper.DEVICE
```

## Backward Compatibility

**Good news!** The old `Config` class still works and delegates to the new Settings system. All existing code continues to function without changes.

```python
# This still works!
from app.core.config import Config

model = Config.WHISPER_MODEL  # Still works, delegates to settings
```

## New Settings Structure

### Main Settings

- `ENVIRONMENT` - Environment name (development, testing, production)
- `DEV` - Development mode flag
- `database` - Database settings (nested)
- `whisper` - WhisperX ML settings (nested)
- `logging` - Logging settings (nested)

### Database Settings (`settings.database`)

- `DB_URL` - Database connection URL
- `DB_ECHO` - Echo SQL queries for debugging

### Whisper Settings (`settings.whisper`)

- `HF_TOKEN` - HuggingFace API token
- `WHISPER_MODEL` - Model size (tiny, base, small, etc.)
- `DEFAULT_LANG` - Default transcription language
- `DEVICE` - Computation device (cuda or cpu)
- `COMPUTE_TYPE` - Compute type (float16, float32, int8)
- `AUDIO_EXTENSIONS` - Supported audio file extensions
- `VIDEO_EXTENSIONS` - Supported video file extensions
- `ALLOWED_EXTENSIONS` - Combined audio and video extensions (computed)

### Logging Settings (`settings.logging`)

- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_FORMAT` - Log format (text or json)
- `FILTER_WARNING` - Filter specific warnings

## Key Features

### Type Safety

All configuration values are properly typed and validated at startup:

```python
settings = get_settings()
# settings.whisper.WHISPER_MODEL is a WhisperModel enum, not a string!
# settings.database.DB_ECHO is a bool, not a string!
```

### Automatic Validation

Invalid configuration causes the application to fail fast at startup with clear error messages:

```python
# If DEVICE=cpu and COMPUTE_TYPE=float16, it auto-corrects to int8
# Invalid enum values raise ValidationError with allowed values
```

### Computed Fields

Some fields are automatically computed:

```python
settings = get_settings()
# ALLOWED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS (computed automatically)
```

### Singleton Pattern

Settings are loaded once and cached:

```python
settings1 = get_settings()
settings2 = get_settings()
assert settings1 is settings2  # True - same instance
```

## Environment Variables

Create a `.env` file in the repository root (see `.env.example` for a complete template):

```bash
# Environment
ENVIRONMENT=development
DEV=true

# Database
DB_URL=sqlite:///records.db

# WhisperX
HF_TOKEN=your-token-here
WHISPER_MODEL=tiny
DEFAULT_LANG=en
DEVICE=cuda
COMPUTE_TYPE=float16

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=text
FILTER_WARNING=true
```

### Nested Configuration (Alternative)

You can also use nested format with `__` separator:

```bash
database__DB_URL=postgresql://localhost/mydb
whisper__WHISPER_MODEL=base
logging__LOG_LEVEL=DEBUG
```

## Migration Path

### For New Code

Use the new Settings system directly:

```python
from app.core.config import get_settings

settings = get_settings()
if settings.whisper.DEVICE == Device.cuda:
    # Use GPU
    pass
```

### For Existing Code

No changes required! The legacy `Config` class continues to work:

```python
from app.core.config import Config

# This continues to work exactly as before
if Config.DEVICE == Device.cuda:
    pass
```

## Testing

### Override Settings in Tests

```python
import os
from app.core.config import Settings, WhisperSettings

def test_with_custom_settings():
    # Set environment variables before creating settings
    os.environ["WHISPER_MODEL"] = "base"
    os.environ["DEVICE"] = "cpu"

    settings = Settings()
    assert settings.whisper.WHISPER_MODEL == WhisperModel.base
    assert settings.whisper.DEVICE == Device.cpu
```

### Using Fixtures

```python
import pytest
from app.core.config import Settings, WhisperSettings
from app.schemas import Device, ComputeType, WhisperModel

@pytest.fixture
def test_settings():
    """Provide test-specific settings."""
    return Settings(
        ENVIRONMENT="testing",
        whisper=WhisperSettings(
            DEVICE=Device.cpu,
            COMPUTE_TYPE=ComputeType.int8,
            WHISPER_MODEL=WhisperModel.tiny
        )
    )

def test_something(test_settings):
    assert test_settings.ENVIRONMENT == "testing"
```

## Troubleshooting

### ValidationError on Startup

If you see a Pydantic ValidationError, it means your configuration is invalid:

```text
ValidationError: 1 validation error for WhisperSettings
COMPUTE_TYPE
  COMPUTE_TYPE must be int8 when DEVICE is cpu
```

**Solution:** Check your `.env` file and ensure all values are valid.

### Circular Import Errors

If you get circular import errors when importing settings:

```python
# BAD - can cause circular imports
from app.core.config import get_settings
settings = get_settings()  # At module level

# GOOD - import inside function
def my_function():
    from app.core.config import get_settings
    settings = get_settings()
```

### Cache Issues in Tests

Settings are cached (singleton). If you need to reload settings in tests:

```python
from app.core.config import get_settings

# Clear the cache
get_settings.cache_clear()

# Now get_settings() will create a new instance
settings = get_settings()
```

## Benefits

1. **Type Safety** - All configuration is typed and validated
2. **Fail Fast** - Invalid configuration causes startup errors, not runtime errors
3. **Self-Documenting** - Field types and defaults are clear in code
4. **IDE Support** - Auto-complete and type checking for configuration
5. **Easy Testing** - Override configuration easily in tests
6. **Environment-Aware** - Different configs per environment
7. **Backward Compatible** - Existing code continues to work

## Additional Resources

- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [.env.example](.env.example) - Complete environment variable template
- [tests/unit/core/test_config.py](tests/unit/core/test_config.py) - Settings usage examples
