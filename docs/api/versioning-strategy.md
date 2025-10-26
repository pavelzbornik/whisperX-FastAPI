# API Versioning Strategy

## Overview

The WhisperX API uses URL path-based versioning to provide controlled evolution while maintaining backward compatibility. All API endpoints (except health checks) are prefixed with `/api/v{major}/`.

**Current Version:** v1.0.0

## Version Format

- **Format:** `/api/v{major}/`
- **Example:** `/api/v1/speech-to-text`
- **Versioning Scheme:** Major version only in URL path

We use **semantic versioning** for the API version number (e.g., v1.0.0), but only the major version appears in the URL path.

## Why URL Path Versioning?

We chose URL path versioning over other approaches for several reasons:

### ✅ Advantages

- **RESTful and visible:** Version is clear in every URL
- **Easy to route and cache:** Simple routing rules and CDN caching
- **Clear in documentation:** Examples are immediately understandable
- **Works with all HTTP clients:** No special headers or configuration needed
- **Browser-friendly:** Can be tested directly in the browser

### ❌ Rejected Alternatives

- **Header-based versioning:** Not visible in URLs, harder to test with browser tools
- **Query parameter versioning:** Not RESTful, unclear, easily forgotten
- **Subdomain versioning:** Complex infrastructure requirements, overkill for this API

## Version Increment Rules

### Major Version (Breaking Changes)

Increment the major version (v1 → v2) for:

- ❌ Removing endpoints
- ❌ Removing request or response fields
- ❌ Changing field types (e.g., string → integer)
- ❌ Changing field semantics (e.g., changing what "language" means)
- ❌ Changing authentication mechanisms
- ❌ Changing HTTP status codes
- ❌ Changing error response structures

### Minor Changes (Non-Breaking)

Do **NOT** increment version for:

- ✅ Adding new endpoints
- ✅ Adding optional request fields
- ✅ Adding response fields
- ✅ Bug fixes
- ✅ Performance improvements
- ✅ Internal refactoring

Minor and patch versions are tracked in the OpenAPI `info.version` field but do not affect the URL path.

## Current API Structure

### Versioned Endpoints

All functional endpoints require the `/api/v1/` prefix:

```
POST /api/v1/speech-to-text              # Complete audio processing
POST /api/v1/speech-to-text-url          # Process from URL
GET  /api/v1/task/all                    # List all tasks
GET  /api/v1/task/{id}                   # Get task status
DELETE /api/v1/task/{id}/delete          # Delete task
POST /api/v1/service/transcribe          # Transcription only
POST /api/v1/service/align               # Alignment only
POST /api/v1/service/diarize             # Diarization only
POST /api/v1/service/combine             # Combine transcript and diarization
```

### Unversioned Endpoints

Health checks remain unversioned with a **stable contract guarantee**:

```
GET /health                              # Overall health check
GET /health/live                         # Liveness probe
GET /health/ready                        # Readiness probe
```

**Why unversioned?** Health checks have a simple, stable contract that will not change in breaking ways. Keeping them unversioned simplifies monitoring and orchestration integrations.

## Deprecation Policy

### Deprecation Timeline

1. **Announcement:** Minimum 6 months notice before end-of-life
2. **Deprecation Period:** Version is marked as deprecated
3. **Support:** Bug fixes only during deprecation period
4. **End-of-Life:** Version is removed from service

### Deprecation Headers (RFC 8594)

When a version is deprecated, the API adds these HTTP headers to all responses:

```http
Deprecation: true
Sunset: 2026-04-22
Link: </api/v2/docs>; rel="successor-version"
```

- **Deprecation:** Boolean indicating the version is deprecated
- **Sunset:** ISO 8601 date when the version will be removed
- **Link:** URL to documentation for the replacement version

### Communication Process

When deprecating a version:

1. ✉️ Email notification to registered API consumers
2. 📝 Update API documentation with deprecation notice
3. 🏷️ Add deprecation headers to API responses
4. 📅 Publish sunset date (minimum 6 months away)
5. 🔗 Provide migration guide to new version

## Version Support

- **Current version (v1):** Fully supported
- **Previous version:** Supported for 6 months after new major version release
- **Older versions:** Not supported

## Version Selection

Clients select the API version via the URL path:

```bash
# Version 1 (current)
curl https://api.example.com/api/v1/speech-to-text

# Future version 2
curl https://api.example.com/api/v2/audio/transcribe
```

There is **no default version.** Clients must explicitly specify the version in every request.

## OpenAPI Documentation

Each API version has its own OpenAPI specification:

- **v1 OpenAPI Spec:** `/api/v1/openapi.json`
- **v1 Swagger UI:** `/api/v1/docs`
- **v1 ReDoc:** `/api/v1/redoc`

The root paths redirect to the current version:

```
/ → /api/v1/docs
/docs → /api/v1/docs
```

## Version Negotiation

### Supported Versions

The API currently supports:

- ✅ **v1:** Current stable version

### Unsupported Versions

Requests to unsupported versions return HTTP 404:

```bash
curl https://api.example.com/api/v2/speech-to-text
# Response: 404 Not Found
# Body: {"detail": "API version v2 not found"}
```

## Migration Between Versions

See the [Migration Guide](migration-guide.md) for detailed instructions on migrating between API versions.

## Implementation Details

### Version Detection Middleware

The `VersionMiddleware` extracts and validates API versions from URL paths:

1. Extract version from URL using regex pattern `/api/v(\d+)/`
2. Validate version against supported versions list
3. Add version to request state for logging and metrics
4. Return 404 for unsupported versions

### Deprecation Middleware

The `DeprecationMiddleware` adds deprecation headers for deprecated versions:

1. Check if request version is deprecated
2. Add RFC 8594 headers if deprecated
3. Log deprecation access for metrics

## Best Practices for API Consumers

1. **Always specify version:** Never assume a default version
2. **Pin to a specific version:** Don't use "latest" in production
3. **Monitor deprecation headers:** Watch for `Deprecation` and `Sunset` headers
4. **Subscribe to notifications:** Register your email for deprecation announcements
5. **Test new versions early:** Upgrade to new versions during deprecation period
6. **Have a rollback plan:** Keep the old version working until new version is validated

## FAQ

### Why not use semantic versioning in the URL?

Including minor and patch versions in URLs (e.g., `/api/v1.2.3/`) would create too many URL variations for what are non-breaking changes. Only major versions represent breaking changes requiring client updates.

### Can I use multiple versions simultaneously?

Yes. Different parts of your application can use different API versions. This allows gradual migration.

### What happens to my requests during version deprecation?

Your requests continue to work normally during the deprecation period. You'll receive deprecation headers warning you about the upcoming sunset date.

### How do I know which version I'm using?

Check the URL path in your API calls. It should contain `/api/v1/`, `/api/v2/`, etc.

### What if I call an endpoint without a version prefix?

Non-versioned paths that aren't health checks will return 404. Health check endpoints (`/health`, `/health/live`, `/health/ready`) remain unversioned and always work.

## Change Log

| Date       | Version | Change                                      |
|------------|---------|---------------------------------------------|
| 2025-10-25 | 1.0.0   | Initial API versioning implementation (v1)  |
