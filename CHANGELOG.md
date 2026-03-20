# Changelog

## [0.5.0](https://github.com/pavelzbornik/whisperX-FastAPI/compare/v0.4.7...v0.5.0) (2026-03-20)


### Features

* **docker:** multi-stage Dockerfile with dedicated dev stage ([507717e](https://github.com/pavelzbornik/whisperX-FastAPI/commit/507717e57f768c66714887f41f6b1c7aa9ebe0d2))


### Bug Fixes

* address PR review comments ([20a44e4](https://github.com/pavelzbornik/whisperX-FastAPI/commit/20a44e4437d4bcfc9a29e634673ed327de94edd1))
* **ci:** always apply latest Docker tag on release events ([945e21f](https://github.com/pavelzbornik/whisperX-FastAPI/commit/945e21fd0cd6b12b1912037dd8837b7e5d585fb1))
* pin attest-build-provenance to SHA and sync ruff to 0.15.7 ([48986d6](https://github.com/pavelzbornik/whisperX-FastAPI/commit/48986d6011bd83631aa967b820ba48a4dd1b7666))
* **test:** use failure-rate threshold in write-path load test ([1a397ea](https://github.com/pavelzbornik/whisperX-FastAPI/commit/1a397ea2e04ee4a990fbcf91b463dd76dcd9ad5d))

## [0.4.7](https://github.com/pavelzbornik/whisperX-FastAPI/compare/v0.4.6...v0.4.7) (2026-03-19)


### Bug Fixes

* **audio:** narrow exception handling and avoid leaking internal error detail ([f472594](https://github.com/pavelzbornik/whisperX-FastAPI/commit/f472594a8ec1bd9254ce63e49d8085583e914523))
* **audio:** return HTTP 400 for unreadable audio files instead of 500 ([9fa7d7d](https://github.com/pavelzbornik/whisperX-FastAPI/commit/9fa7d7d15c59d12c4f278be923c7094d8eadbdf4))
* **ci:** register omegaconf safe globals for PyTorch 2.6 compatibility ([23ab7f3](https://github.com/pavelzbornik/whisperX-FastAPI/commit/23ab7f36c94338834fb7a20987cec70b4a1ceb34))
* **deps:** disable dependency dashboard approval gate ([2853039](https://github.com/pavelzbornik/whisperX-FastAPI/commit/285303970f16235597476115fd435f3bfaa9ddd3))
* **deps:** fix invalid Renovate configuration ([5d1dfdd](https://github.com/pavelzbornik/whisperX-FastAPI/commit/5d1dfdd81bf202eb25b08c6d3b88ba85e4d1e229))
* **renovate:** override Mend platform mode=silent to enable PR creation ([1a303d5](https://github.com/pavelzbornik/whisperX-FastAPI/commit/1a303d530d9ed1d2abac0352bde4223125b9a88f))

## [0.4.6](https://github.com/pavelzbornik/whisperX-FastAPI/compare/v0.4.5...v0.4.6) (2026-03-13)


### Bug Fixes

* correct YAML list indentation in uvicorn log config ([ea4dc46](https://github.com/pavelzbornik/whisperX-FastAPI/commit/ea4dc46949225e3f6876c77290cf464ed4255d43))


### Documentation

* add Claude Code project documentation guides ([d764900](https://github.com/pavelzbornik/whisperX-FastAPI/commit/d7649006ef43a22a6e38095ea5a9f3ed4cd68e3a))

## [0.4.5](https://github.com/pavelzbornik/whisperX-FastAPI/compare/v0.4.4...v0.4.5) (2026-01-08)


### Bug Fixes

* address PR review comments ([d9e45c5](https://github.com/pavelzbornik/whisperX-FastAPI/commit/d9e45c549eb2cb83cfed61edec463524d9cb7065))
* correct table header formatting in db_schema.md and exception-handling.md ([f1dcfea](https://github.com/pavelzbornik/whisperX-FastAPI/commit/f1dcfeaaa99aec610602164692643f580f76e77a))
* downgrade CUDA version in Dockerfile to 13.0.1 ([c6ad4cc](https://github.com/pavelzbornik/whisperX-FastAPI/commit/c6ad4cc60f969b672f3173a0b141cb7f0b20d02f))
* increase health check wait time and improve error logging in CI workflow; add curl to Dockerfile ([2ae089f](https://github.com/pavelzbornik/whisperX-FastAPI/commit/2ae089febce0042eb514fd65cae4b42e49710cd6))
* replace datetime.utcnow() with timezone-aware datetime.now(timezone.utc) ([25e519b](https://github.com/pavelzbornik/whisperX-FastAPI/commit/25e519b77b797f12f1aecfd283b37b168a742bba))
* revert CUDA base image version to 13.0.1 ([cf47db0](https://github.com/pavelzbornik/whisperX-FastAPI/commit/cf47db0da77328e89c2c818adce955b8b238b196))


### Documentation

* **issue-templates:** add Copilot Story issue template with TDD and testing standards ([dbfe2c6](https://github.com/pavelzbornik/whisperX-FastAPI/commit/dbfe2c6e0108d4e0fe7bfe6a4bfa91298f763e3b))

## [0.4.4](https://github.com/pavelzbornik/whisperX-FastAPI/compare/v0.4.3...v0.4.4) (2025-12-15)


### Bug Fixes

* correct table header formatting in db_schema.md and exception-handling.md ([e346fc2](https://github.com/pavelzbornik/whisperX-FastAPI/commit/e346fc298c58262b166b82abd481485cc1a6191c))
* increase health check wait time and improve error logging in CI workflow; add curl to Dockerfile ([fd11d0c](https://github.com/pavelzbornik/whisperX-FastAPI/commit/fd11d0cb04ead1ce06b07018c53905c1471656ca))

## [0.4.3](https://github.com/pavelzbornik/whisperX-FastAPI/compare/v0.4.2...v0.4.3) (2025-10-26)


### Documentation

* **issue-templates:** add Copilot Story issue template with TDD and testing standards ([f7af931](https://github.com/pavelzbornik/whisperX-FastAPI/commit/f7af93121a2b8badb5cbf80ac65227ad8430842c))

## [0.4.2](https://github.com/pavelzbornik/whisperX-FastAPI/compare/v0.4.1...v0.4.2) (2025-10-26)


### Documentation

* **issue-templates:** add Copilot Story issue template with TDD and testing standards ([1d88ad2](https://github.com/pavelzbornik/whisperX-FastAPI/commit/1d88ad20d4454156f431a16a835537b187c12bfb))

## [0.4.1](https://github.com/pavelzbornik/whisperX-FastAPI/compare/v0.4.0...v0.4.1) (2025-10-24)

### Bug Fixes

* address PR review comments ([a80612e](https://github.com/pavelzbornik/whisperX-FastAPI/commit/a80612e841b4eb4850d23de60b425d91e5fffb6e))

## [0.3.1](https://github.com/pavelzbornik/whisperX-FastAPI/compare/v0.3.0...v0.3.1) (2025-10-23)

### Bug Fixes

* update GitHub token reference from GITHUB_TOKEN to PAT_TOKEN in CI workflow ([cc844e6](https://github.com/pavelzbornik/whisperX-FastAPI/commit/cc844e6f9f8a4c73deecbcec51d4f1a0243aa9ce))
