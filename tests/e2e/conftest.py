"""E2E-wide fixtures: parametrised TestClient over SQLite and PostgreSQL."""

import asyncio
import os
import socket
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool


def _pg_available() -> bool:
    """Return True if the PostgreSQL sidecar is reachable on port 5432."""
    try:
        socket.create_connection(("postgres", 5432), timeout=1).close()
        return True
    except OSError:
        return False


def _async_url(url: str) -> str:
    """Rewrite a sync URL to its async-driver equivalent if needed."""
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return url.replace("://", "+asyncpg://", 1)
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def _sync_url(url: str) -> str:
    """Rewrite an async URL back to a plain sync URL if needed."""
    return (
        url.replace("+asyncpg", "")
        .replace("+aiosqlite", "")
        .replace("postgresql+", "postgresql")
    )


def _make_async_engine(db_url: str):
    """Build an async engine appropriate for the given URL."""
    kwargs: dict[str, Any] = {"echo": False}
    if db_url.startswith("sqlite"):
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
        kwargs["pool_pre_ping"] = True
    return create_async_engine(db_url, **kwargs)


def _make_sync_engine(db_url: str):
    """Build a sync engine appropriate for the given URL (used by background tasks)."""
    kwargs: dict[str, Any] = {"echo": False}
    if db_url.startswith("sqlite"):
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
        kwargs["pool_pre_ping"] = True
    return create_engine(db_url, **kwargs)


@pytest.fixture(
    scope="module",
    params=[
        pytest.param("sqlite", id="sqlite"),
        pytest.param(
            "postgresql",
            id="postgresql",
            marks=pytest.mark.skipif(
                not _pg_available(),
                reason="PostgreSQL sidecar not reachable on postgres:5432",
            ),
        ),
    ],
)
def client(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[TestClient, None, None]:
    """Parametrised TestClient over SQLite and PostgreSQL.

    Each test module that uses this fixture is executed twice — once against a
    temporary SQLite file and once against the PostgreSQL sidecar.  The
    PostgreSQL variant is automatically skipped when the sidecar is unreachable
    (e.g. plain CI without the docker-compose stack).

    The fixture:
    - Creates a fresh async engine + sync engine for the parametrised database.
    - Creates the schema via ``Base.metadata.create_all``.
    - Patches ``app.main.async_engine`` so the lifespan and health endpoints
      hit the right database.
    - Overrides the DI container's ``db_session_factory`` so every
      request-scoped async session uses the right engine.
    - Patches ``SyncSessionLocal`` in ``audio_processing_service`` so background
      tasks (which run in a thread pool with a sync session) also write to the
      same database.
    - Opens ``TestClient`` as a context manager so all requests share a single
      anyio event loop (required for asyncpg connection pooling).

    Yields:
        TestClient: Configured test client for the parametrised database.
    """
    import app.main as main_module
    import app.services.audio_processing_service as audio_svc_module
    import app.services.whisperx_wrapper_service as whisperx_svc_module
    from app.infrastructure.database.models import Base

    if request.param == "sqlite":
        db_file = tmp_path_factory.mktemp("e2e") / "test.db"
        async_db_url = f"sqlite+aiosqlite:///{db_file}"
        sync_db_url = f"sqlite:///{db_file}"
    else:
        raw = os.environ.get(
            "TEST_DB_URL", "postgresql://postgres:test@postgres/testdb"
        )
        async_db_url = _async_url(raw)
        sync_db_url = _sync_url(async_db_url)

    async_engine = _make_async_engine(async_db_url)
    sync_engine = _make_sync_engine(sync_db_url)

    session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    sync_session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=sync_engine
    )

    # Create schema, then dispose so no connections leak into the test's loop.
    async def _create_tables() -> None:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await async_engine.dispose()

    asyncio.run(_create_tables())

    # Patch app.main's module-level async_engine so the lifespan
    # (create_all + dispose) and /health/ready hit the right database.
    original_main_engine = main_module.async_engine
    main_module.async_engine = async_engine

    # Patch the sync session used by background task services so they write
    # task results to the same database as the async engine.
    original_audio_sync_session = audio_svc_module.SyncSessionLocal
    original_whisperx_sync_session = whisperx_svc_module.SyncSessionLocal
    audio_svc_module.SyncSessionLocal = sync_session_factory
    whisperx_svc_module.SyncSessionLocal = sync_session_factory

    # Override the DI container so request-scoped async sessions use our engine.
    container = main_module.container
    container.db_engine.override(providers.Singleton(lambda: async_engine))
    container.db_session_factory.override(providers.Factory(session_factory))

    # Suppress docs generation so the lifespan does not rewrite openapi.json /
    # openapi.yaml / db_schema.md on every test run (which would dirty the
    # working tree and cause the pre-push hook to fail).
    with (
        patch("app.main.save_openapi_json"),
        patch("app.main.generate_db_schema"),
        TestClient(main_module.app, follow_redirects=False) as c,
    ):
        yield c

    # Restore everything after the module finishes.
    container.db_engine.reset_override()
    container.db_session_factory.reset_override()
    main_module.async_engine = original_main_engine
    audio_svc_module.SyncSessionLocal = original_audio_sync_session
    whisperx_svc_module.SyncSessionLocal = original_whisperx_sync_session
