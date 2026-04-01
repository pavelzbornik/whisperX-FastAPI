"""Tests for Annotated dependency injection usage in the API layer."""

import inspect
from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin, get_type_hints

import pytest
from fastapi.params import Depends

from app.api import audio_api, audio_services_api, dependencies, task_api


def _assert_depends_annotated(
    hints: dict[str, Any],
    parameter_name: str,
    dependency_callable: Callable[..., Any] | None = None,
) -> None:
    """Assert that a parameter uses an Annotated FastAPI dependency."""
    annotation = hints[parameter_name]
    assert get_origin(annotation) is Annotated
    _, *metadata = get_args(annotation)
    depends_markers = [item for item in metadata if isinstance(item, Depends)]
    assert len(depends_markers) == 1
    if dependency_callable is not None:
        assert depends_markers[0].dependency is dependency_callable


@pytest.mark.unit
@pytest.mark.parametrize(
    ("alias_name", "dependency_callable"),
    [
        ("TaskRepositoryDependency", dependencies.get_task_repository),
        ("FileServiceDependency", dependencies.get_file_service),
        ("TaskManagementServiceDependency", dependencies.get_task_management_service),
        ("TranscriptionServiceDependency", dependencies.get_transcription_service),
        ("DiarizationServiceDependency", dependencies.get_diarization_service),
        ("AlignmentServiceDependency", dependencies.get_alignment_service),
        (
            "SpeakerAssignmentServiceDependency",
            dependencies.get_speaker_assignment_service,
        ),
    ],
)
def test_dependency_aliases_use_annotated(
    alias_name: str, dependency_callable: Callable[..., Any]
) -> None:
    """Dependency aliases should wrap the provider in Annotated metadata."""
    alias = getattr(dependencies, alias_name)

    assert get_origin(alias) is Annotated
    dependency_type, *metadata = get_args(alias)
    assert dependency_type is not None
    depends_markers = [item for item in metadata if isinstance(item, Depends)]
    assert len(depends_markers) == 1
    assert depends_markers[0].dependency is dependency_callable


@pytest.mark.unit
@pytest.mark.parametrize(
    ("endpoint", "dependent_parameters"),
    [
        (
            audio_api.speech_to_text,
            [
                "model_params",
                "align_params",
                "diarize_params",
                "asr_options_params",
                "vad_options_params",
                "callback_url",
                "repository",
                "file_service",
            ],
        ),
        (
            audio_api.speech_to_text_url,
            [
                "model_params",
                "align_params",
                "diarize_params",
                "asr_options_params",
                "vad_options_params",
                "callback_url",
                "repository",
                "file_service",
            ],
        ),
        (
            audio_services_api.transcribe,
            [
                "model_params",
                "asr_options_params",
                "vad_options_params",
                "repository",
                "file_service",
                "transcription_service",
            ],
        ),
        (
            audio_services_api.align,
            ["align_params", "repository", "file_service", "alignment_service"],
        ),
        (
            audio_services_api.diarize,
            [
                "repository",
                "diarize_params",
                "file_service",
                "diarization_service",
            ],
        ),
        (
            audio_services_api.combine,
            ["repository", "file_service", "speaker_service"],
        ),
        (task_api.get_all_tasks_status, ["service"]),
        (task_api.get_transcription_status, ["service"]),
        (task_api.delete_task, ["service"]),
    ],
)
def test_api_endpoints_use_annotated_dependencies(
    endpoint: Callable[..., Any], dependent_parameters: list[str]
) -> None:
    """API endpoints should expose dependencies through Annotated annotations."""
    signature = inspect.signature(endpoint)
    hints = get_type_hints(endpoint, include_extras=True)

    for parameter_name in dependent_parameters:
        _assert_depends_annotated(hints, parameter_name)
        assert signature.parameters[parameter_name].default is inspect.Parameter.empty
