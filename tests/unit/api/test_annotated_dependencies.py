"""Tests for Annotated dependency injection usage in the API layer.

The API layer injects services via ``Annotated`` aliases exported from
``app.api.dependencies`` rather than ``Depends(...)`` defaults. These tests pin
that convention so a new route cannot silently reintroduce the old style.
"""

import inspect
from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin, get_type_hints

import pytest
from fastapi.params import Depends

from app.api import (
    audio_api,
    audio_services_api,
    dependencies,
    openai_compat_api,
    speaker_api,
    task_api,
)

# Every module that defines routes, and therefore must follow the convention.
ROUTER_MODULES = [
    audio_api,
    audio_services_api,
    openai_compat_api,
    speaker_api,
    task_api,
]

# Alias name -> provider it must resolve to.
ALIASES = [
    ("TaskRepositoryDep", dependencies.get_task_repository),
    ("FileServiceDep", dependencies.get_file_service),
    ("TaskManagementServiceDep", dependencies.get_task_management_service),
    ("TranscriptionServiceDep", dependencies.get_transcription_service),
    ("DiarizationServiceDep", dependencies.get_diarization_service),
    ("AlignmentServiceDep", dependencies.get_alignment_service),
    ("SpeakerAssignmentServiceDep", dependencies.get_speaker_assignment_service),
    ("SpeakerServiceDep", dependencies.get_speaker_service),
]


def _unwrap(endpoint: Callable[..., Any]) -> Callable[..., Any]:
    """Return the undecorated endpoint behind any rate-limit wrapper."""
    return inspect.unwrap(endpoint)


@pytest.mark.unit
@pytest.mark.parametrize(("alias_name", "provider"), ALIASES)
def test_dependency_alias_wraps_expected_provider(
    alias_name: str, provider: Callable[..., Any]
) -> None:
    """Each alias is an ``Annotated`` type carrying exactly one provider."""
    alias = getattr(dependencies, alias_name)

    assert get_origin(alias) is Annotated

    injected_type, *metadata = get_args(alias)
    assert injected_type is not None

    markers = [item for item in metadata if isinstance(item, Depends)]
    assert len(markers) == 1
    assert markers[0].dependency is provider


@pytest.mark.unit
def test_every_alias_is_exported() -> None:
    """The alias list above stays in sync with the module."""
    exported = {
        name
        for name in vars(dependencies)
        if name.endswith("Dep") and get_origin(getattr(dependencies, name)) is Annotated
    }
    assert exported == {name for name, _ in ALIASES}


@pytest.mark.unit
@pytest.mark.parametrize("module", ROUTER_MODULES, ids=lambda m: m.__name__)
def test_routes_do_not_use_depends_defaults_for_services(module: Any) -> None:
    """No route injects a container service through a ``Depends`` default.

    Parameter *defaults* built from ``app.api.dependencies`` providers are the
    pattern the ``Annotated`` aliases replace. Other ``Depends()`` defaults —
    Pydantic query-parameter models and the callback-URL validator — are left
    alone, so this check targets only the container-backed providers.
    """
    providers = {provider for _, provider in ALIASES}

    offenders = []
    for name, func in vars(module).items():
        if not callable(func) or not hasattr(func, "__code__"):
            continue
        target = _unwrap(func)
        try:
            signature = inspect.signature(target)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            continue
        for param_name, param in signature.parameters.items():
            default = param.default
            if isinstance(default, Depends) and default.dependency in providers:
                offenders.append(f"{name}.{param_name}")

    assert offenders == []


@pytest.mark.unit
@pytest.mark.parametrize("module", ROUTER_MODULES, ids=lambda m: m.__name__)
def test_injected_service_parameters_are_annotated(module: Any) -> None:
    """Where a route takes a container service, it does so via ``Annotated``."""
    # Compared by identity: some annotations in these modules are unhashable,
    # so a set membership test would raise instead of simply not matching.
    alias_types = [getattr(dependencies, name) for name, _ in ALIASES]

    for name, func in vars(module).items():
        if not callable(func) or not hasattr(func, "__code__"):
            continue
        target = _unwrap(func)
        try:
            hints = get_type_hints(target, include_extras=True)
        except (NameError, TypeError):  # pragma: no cover - defensive
            continue
        for param_name, annotation in hints.items():
            if not any(annotation is alias for alias in alias_types):
                continue
            assert get_origin(annotation) is Annotated, (
                f"{module.__name__}.{name}.{param_name} lost its Annotated alias"
            )
