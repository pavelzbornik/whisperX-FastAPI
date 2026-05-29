# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in whisperX-FastAPI, please report it as soon as possible to help keep the community safe.

- **Do not** open public issues for security vulnerabilities.
- Instead, please email the project maintainers at the contact address listed in the repository or use the GitHub security advisory feature.
- Provide as much detail as possible to help us quickly understand and address the issue.

We will investigate all reports and do our best to fix valid issues promptly. Once the vulnerability is resolved, we will coordinate disclosure with the reporter and acknowledge their contribution if desired.

## Supported Versions

We support only the latest stable release from the `main` branch (latest `v*` tag). Please ensure you are using the most recent tagged version before reporting a vulnerability.

## Best Practices

- Always keep your dependencies up to date.
- Use strong, unique credentials for all services.

## Known Advisories in ML Dependencies

The transcription and diarization stack pulls in deep transitive machine-learning
dependencies (`whisperx` → `pyannote-audio`, `transformers`). Two Dependabot advisories
currently have **no safe remediation** and have been assessed and accepted as
non-exploitable in this service's usage:

| Advisory | Package (transitive via) | Why it is not remediated | Why it is not exploitable here |
| --- | --- | --- | --- |
| [GHSA-75m9-98v2-hjpm](https://github.com/advisories/GHSA-75m9-98v2-hjpm) — insecure checkpoint deserialization in `load_from_checkpoint` | `pytorch-lightning` (`pyannote-audio`) | No patched version exists yet — the entire affected range (`<= 2.6.0`) has no fix. | Diarization models are loaded only from the configured, trusted Hugging Face repositories (gated by `HF_TOKEN`). Checkpoints are never sourced from API request data or untrusted user input. |
| [GHSA-69w3-r845-3855](https://github.com/advisories/GHSA-69w3-r845-3855) — arbitrary code execution in the `Trainer` class | `transformers` (`whisperx`) | The only fix is `5.0.0rc3`, a pre-release major release incompatible with `whisperx` 3.8.5 (built for `transformers` 4.x). | This is an inference-only service; it never instantiates `transformers.Trainer`. |

These advisories are re-evaluated whenever Renovate opens a security update PR, and will
be upgraded as soon as a compatible, stable patched release is available.

Thank you for helping keep whisperX-FastAPI and its users secure!
