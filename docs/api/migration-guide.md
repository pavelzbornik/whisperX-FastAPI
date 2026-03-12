# API Migration Guide

## Overview

This guide helps you migrate your client applications to use the versioned WhisperX API. All API endpoints now require the `/api/v1/` prefix.

## Migration from Unversioned to v1

### Summary of Changes

**All functional endpoints now use the `/api/v1/` prefix**

- Health check endpoints (`/health`, `/health/live`, `/health/ready`) remain unchanged
- All other endpoints require `/api/v1/` prefix
- OpenAPI documentation moved to `/api/v1/docs`

### Breaking Changes

None. The v1 API maintains full backward compatibility with the unversioned API behavior. The only change is the URL path prefix.

## Updated Endpoints

### Speech-to-Text Endpoints

#### Complete Audio Processing

**Before:**

```bash
POST /speech-to-text
```

**After:**

```bash
POST /api/v1/speech-to-text
```

**Example:**

```bash
# Old (no longer works)
curl -X POST "https://api.example.com/speech-to-text" \
  -F "file=@audio.mp3"

# New (v1)
curl -X POST "https://api.example.com/api/v1/speech-to-text" \
  -F "file=@audio.mp3"
```

#### Process from URL

**Before:**

```bash
POST /speech-to-text-url
```

**After:**

```bash
POST /api/v1/speech-to-text-url
```

**Example:**

```bash
# Old
curl -X POST "https://api.example.com/speech-to-text-url" \
  -F "url=https://example.com/audio.mp3"

# New
curl -X POST "https://api.example.com/api/v1/speech-to-text-url" \
  -F "url=https://example.com/audio.mp3"
```

### Task Management Endpoints

#### Get All Tasks

**Before:**

```bash
GET /task/all
```

**After:**

```bash
GET /api/v1/task/all
```

#### Get Task Status

**Before:**

```bash
GET /task/{id}
```

**After:**

```bash
GET /api/v1/task/{id}
```

#### Delete Task

**Before:**

```bash
DELETE /task/{id}/delete
```

**After:**

```bash
DELETE /api/v1/task/{id}/delete
```

**Example:**

```bash
# Old
curl "https://api.example.com/task/abc-123"

# New
curl "https://api.example.com/api/v1/task/abc-123"
```

### Service Endpoints

#### Transcription Service

**Before:**

```bash
POST /service/transcribe
```

**After:**

```bash
POST /api/v1/service/transcribe
```

#### Alignment Service

**Before:**

```bash
POST /service/align
```

**After:**

```bash
POST /api/v1/service/align
```

#### Diarization Service

**Before:**

```bash
POST /service/diarize
```

**After:**

```bash
POST /api/v1/service/diarize
```

#### Combine Service

**Before:**

```bash
POST /service/combine
```

**After:**

```bash
POST /api/v1/service/combine
```

**Example:**

```bash
# Old
curl -X POST "https://api.example.com/service/transcribe" \
  -F "file=@audio.mp3"

# New
curl -X POST "https://api.example.com/api/v1/service/transcribe" \
  -F "file=@audio.mp3"
```

### Health Check Endpoints (Unchanged)

These endpoints remain at the root level with no version prefix:

```bash
GET /health          # No change
GET /health/live     # No change
GET /health/ready    # No change
```

**Why?** Health checks have a stable contract and are used by monitoring systems that expect consistent endpoints.

## Client Migration Examples

### Python Client

**Before:**

```python
import requests

BASE_URL = "https://api.example.com"

# Submit transcription task
response = requests.post(
    f"{BASE_URL}/speech-to-text",
    files={"file": open("audio.mp3", "rb")}
)
task_id = response.json()["identifier"]

# Check task status
response = requests.get(f"{BASE_URL}/task/{task_id}")
result = response.json()
```

**After:**

```python
import requests

BASE_URL = "https://api.example.com/api/v1"  # Add version prefix

# Submit transcription task
response = requests.post(
    f"{BASE_URL}/speech-to-text",
    files={"file": open("audio.mp3", "rb")}
)
task_id = response.json()["identifier"]

# Check task status
response = requests.get(f"{BASE_URL}/task/{task_id}")
result = response.json()
```

**Or use environment variable:**

```python
import os
import requests

API_VERSION = os.getenv("WHISPERX_API_VERSION", "v1")
BASE_URL = f"https://api.example.com/api/{API_VERSION}"

# Rest of the code unchanged
```

### JavaScript Client

**Before:**

```javascript
const BASE_URL = 'https://api.example.com';

// Submit transcription task
const formData = new FormData();
formData.append('file', audioFile);

const response = await fetch(`${BASE_URL}/speech-to-text`, {
  method: 'POST',
  body: formData
});
const { identifier } = await response.json();

// Check task status
const taskResponse = await fetch(`${BASE_URL}/task/${identifier}`);
const result = await taskResponse.json();
```

**After:**

```javascript
const BASE_URL = 'https://api.example.com/api/v1';  // Add version prefix

// Submit transcription task
const formData = new FormData();
formData.append('file', audioFile);

const response = await fetch(`${BASE_URL}/speech-to-text`, {
  method: 'POST',
  body: formData
});
const { identifier } = await response.json();

// Check task status
const taskResponse = await fetch(`${BASE_URL}/task/${identifier}`);
const result = await taskResponse.json();
```

### cURL Scripts

**Before:**

```bash
#!/bin/bash
API_URL="https://api.example.com"

curl -X POST "$API_URL/speech-to-text" \
  -F "file=@audio.mp3"
```

**After:**

```bash
#!/bin/bash
API_URL="https://api.example.com/api/v1"  # Add version prefix

curl -X POST "$API_URL/speech-to-text" \
  -F "file=@audio.mp3"
```

### Configuration Files

If you store API endpoints in configuration files, update them:

**Before (config.yaml):**

```yaml
whisperx:
  base_url: https://api.example.com
  endpoints:
    transcribe: /speech-to-text
    task_status: /task/{id}
```

**After (config.yaml):**

```yaml
whisperx:
  base_url: https://api.example.com
  api_version: v1
  endpoints:
    transcribe: /api/v1/speech-to-text
    task_status: /api/v1/task/{id}
```

## Documentation Access

### API Documentation

**Before:**

```
https://api.example.com/docs
```

**After:**

```
https://api.example.com/api/v1/docs
```

The old `/docs` URL now redirects to `/api/v1/docs`.

### OpenAPI Specification

**Before:**

```
https://api.example.com/openapi.json
```

**After:**

```
https://api.example.com/api/v1/openapi.json
```

## Migration Checklist

Use this checklist to ensure complete migration:

- [ ] **Update base URL** to include `/api/v1` prefix
- [ ] **Update all endpoint paths** to use versioned URLs
- [ ] **Keep health check URLs unchanged** (no version prefix)
- [ ] **Update documentation links** to versioned docs
- [ ] **Update configuration files** with new paths
- [ ] **Update environment variables** if used
- [ ] **Test all API integrations** with new URLs
- [ ] **Update monitoring/alerting** if they reference specific endpoints
- [ ] **Update saved scripts/automation** with new paths
- [ ] **Update team documentation** with migration guide
- [ ] **Notify dependent services** of the change

## Testing Your Migration

### Manual Testing

Test each endpoint you use:

```bash
# Test speech-to-text
curl -X POST "https://api.example.com/api/v1/speech-to-text" \
  -F "file=@test-audio.mp3"

# Test task retrieval
curl "https://api.example.com/api/v1/task/abc-123"

# Test health check (should still work without version)
curl "https://api.example.com/health"
```

### Automated Testing

Update your test suites:

```python
# Before
def test_transcribe():
    response = client.post("/speech-to-text", files={"file": audio})
    assert response.status_code == 200

# After
def test_transcribe():
    response = client.post("/api/v1/speech-to-text", files={"file": audio})
    assert response.status_code == 200
```

## Common Migration Issues

### Issue: 404 Not Found

**Symptom:** Requests return 404 error

**Cause:** Using old unversioned endpoints

**Solution:** Add `/api/v1/` prefix to all non-health endpoints

```bash
# Wrong
curl "https://api.example.com/task/abc-123"
# Returns: 404 Not Found

# Correct
curl "https://api.example.com/api/v1/task/abc-123"
# Returns: 200 OK
```

### Issue: Health Checks Failing

**Symptom:** Monitoring shows health checks as failed

**Cause:** Adding version prefix to health check endpoints

**Solution:** Keep health checks without version prefix

```bash
# Wrong
curl "https://api.example.com/api/v1/health"
# Returns: 404 Not Found

# Correct
curl "https://api.example.com/health"
# Returns: 200 OK
```

### Issue: Documentation Not Loading

**Symptom:** Documentation page shows 404

**Cause:** Using old documentation URL

**Solution:** Use versioned docs URL or allow redirect

```bash
# Old URL (redirects to new URL)
https://api.example.com/docs

# New URL (recommended)
https://api.example.com/api/v1/docs
```

## Rollback Plan

If you encounter issues during migration, you can temporarily rollback by:

1. Revert code changes to use old endpoint paths
2. Monitor for resolution of issues
3. Plan migration for lower-traffic period
4. Contact support if persistent issues occur

**Note:** The unversioned API endpoints are deprecated and will be removed in a future release. Complete migration to v1 as soon as possible.

## Support and Questions

If you encounter issues during migration:

1. Check the [Versioning Strategy](versioning-strategy.md) documentation
2. Review the [API Documentation](https://api.example.com/api/v1/docs)
3. Check for known issues in the GitHub repository
4. Contact support with specific error messages and request examples

## Future Migrations

When migrating to future API versions (e.g., v2):

1. Review the version-specific migration guide
2. Test against the new version in parallel
3. Update your code gradually
4. Monitor for deprecation headers on v1 responses
5. Complete migration before the sunset date

Example of using v2 (when available):

```python
# v1 (current)
BASE_URL = "https://api.example.com/api/v1"

# v2 (future)
BASE_URL = "https://api.example.com/api/v2"
```

You can run both versions simultaneously during the transition period.

## Summary

The migration to v1 is straightforward:

1. **Add `/api/v1/` prefix** to all functional endpoints
2. **Keep health checks unchanged** (no prefix)
3. **Test thoroughly** before deploying
4. **Update documentation** and team knowledge

This migration ensures your application can benefit from future API improvements while maintaining backward compatibility.
