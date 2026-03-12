"""Unit tests for SQLAlchemyUnitOfWork and AsyncSQLAlchemyUnitOfWork."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.database.unit_of_work import (
    AsyncSQLAlchemyUnitOfWork,
    SQLAlchemyUnitOfWork,
)


@pytest.mark.unit
class TestSQLAlchemyUnitOfWork:
    """Unit tests for the sync SQLAlchemyUnitOfWork."""

    @patch(
        "app.infrastructure.database.unit_of_work.SyncSessionLocal",
        return_value=MagicMock(),
    )
    def test_enter_creates_session_and_repository(
        self, mock_session_local: MagicMock
    ) -> None:
        """Test __enter__ sets up session and tasks repository."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        with SQLAlchemyUnitOfWork() as uow:
            assert uow.tasks is not None
            assert uow._session is mock_session

    def test_enter_reuses_provided_session(self) -> None:
        """Test __enter__ uses provided session instead of creating new one."""
        mock_session = MagicMock()

        with SQLAlchemyUnitOfWork(session=mock_session) as uow:
            assert uow._session is mock_session

    def test_commit_commits_session_and_sets_flag(self) -> None:
        """Test commit() calls session.commit and sets _committed flag."""
        mock_session = MagicMock()

        with SQLAlchemyUnitOfWork(session=mock_session) as uow:
            uow.commit()
            mock_session.commit.assert_called_once()
            assert uow._committed is True

    def test_exit_without_commit_rolls_back(self) -> None:
        """Test exiting without commit triggers rollback."""
        mock_session = MagicMock()

        with SQLAlchemyUnitOfWork(session=mock_session):
            pass  # no commit

        mock_session.rollback.assert_called()

    def test_exit_on_exception_rolls_back(self) -> None:
        """Test exception inside context triggers rollback."""
        mock_session = MagicMock()

        with pytest.raises(ValueError):
            with SQLAlchemyUnitOfWork(session=mock_session):
                raise ValueError("test error")

        mock_session.rollback.assert_called()

    def test_exit_closes_session_when_created_internally(self) -> None:
        """Test that internally-created sessions are closed on exit."""
        mock_session = MagicMock()
        with patch(
            "app.infrastructure.database.unit_of_work.SyncSessionLocal",
            return_value=mock_session,
        ):
            with SQLAlchemyUnitOfWork() as uow:
                uow.commit()
            mock_session.close.assert_called_once()

    def test_exit_does_not_close_externally_provided_session(self) -> None:
        """Test that externally provided sessions are not closed on exit."""
        mock_session = MagicMock()

        with SQLAlchemyUnitOfWork(session=mock_session) as uow:
            uow.commit()

        mock_session.close.assert_not_called()

    def test_rollback_calls_session_rollback(self) -> None:
        """Test rollback() delegates to session.rollback."""
        mock_session = MagicMock()

        with SQLAlchemyUnitOfWork(session=mock_session) as uow:
            uow.rollback()
            mock_session.rollback.assert_called_once()
            uow._committed = True  # prevent double rollback on exit


@pytest.mark.unit
class TestAsyncSQLAlchemyUnitOfWork:
    """Unit tests for the async AsyncSQLAlchemyUnitOfWork."""

    @patch(
        "app.infrastructure.database.unit_of_work.AsyncSessionLocal",
        return_value=AsyncMock(),
    )
    async def test_aenter_creates_session_and_repository(
        self, mock_session_local: AsyncMock
    ) -> None:
        """Test __aenter__ sets up session and tasks repository."""
        mock_session = AsyncMock()
        mock_session_local.return_value = mock_session

        async with AsyncSQLAlchemyUnitOfWork() as uow:
            assert uow.tasks is not None
            assert uow._session is mock_session

    async def test_aenter_reuses_provided_session(self) -> None:
        """Test __aenter__ uses provided session instead of creating new one."""
        mock_session = AsyncMock()

        async with AsyncSQLAlchemyUnitOfWork(session=mock_session) as uow:
            assert uow._session is mock_session

    async def test_commit_commits_session_and_sets_flag(self) -> None:
        """Test commit() calls session.commit and sets _committed flag."""
        mock_session = AsyncMock()

        async with AsyncSQLAlchemyUnitOfWork(session=mock_session) as uow:
            await uow.commit()
            mock_session.commit.assert_awaited_once()
            assert uow._committed is True

    async def test_aexit_without_commit_rolls_back(self) -> None:
        """Test exiting without commit triggers rollback."""
        mock_session = AsyncMock()

        async with AsyncSQLAlchemyUnitOfWork(session=mock_session):
            pass  # no commit

        mock_session.rollback.assert_awaited()

    async def test_aexit_on_exception_rolls_back(self) -> None:
        """Test exception inside async context triggers rollback."""
        mock_session = AsyncMock()

        with pytest.raises(ValueError):
            async with AsyncSQLAlchemyUnitOfWork(session=mock_session):
                raise ValueError("test error")

        mock_session.rollback.assert_awaited()

    async def test_aexit_closes_session_when_created_internally(self) -> None:
        """Test that internally-created sessions are closed on exit."""
        mock_session = AsyncMock()
        with patch(
            "app.infrastructure.database.unit_of_work.AsyncSessionLocal",
            return_value=mock_session,
        ):
            async with AsyncSQLAlchemyUnitOfWork() as uow:
                await uow.commit()
            mock_session.close.assert_awaited_once()

    async def test_aexit_does_not_close_externally_provided_session(self) -> None:
        """Test that externally provided sessions are not closed on exit."""
        mock_session = AsyncMock()

        async with AsyncSQLAlchemyUnitOfWork(session=mock_session) as uow:
            await uow.commit()

        mock_session.close.assert_not_awaited()

    async def test_rollback_calls_session_rollback(self) -> None:
        """Test rollback() delegates to session.rollback."""
        mock_session = AsyncMock()

        async with AsyncSQLAlchemyUnitOfWork(session=mock_session) as uow:
            await uow.rollback()
            mock_session.rollback.assert_awaited_once()
            uow._committed = True  # prevent double rollback on exit
