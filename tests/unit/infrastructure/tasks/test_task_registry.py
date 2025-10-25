"""Tests for TaskRegistry."""

import pytest

from app.infrastructure.tasks.task_registry import TaskRegistry


class TestTaskRegistry:
    """Test suite for TaskRegistry."""

    def test_create_registry(self) -> None:
        """Test creating an empty registry."""
        registry = TaskRegistry()
        assert registry.list_task_types() == []

    def test_register_handler(self) -> None:
        """Test registering a task handler."""
        registry = TaskRegistry()

        def test_handler(param: str) -> dict[str, str]:
            return {"result": param}

        registry.register("test_task", test_handler)

        assert registry.is_registered("test_task")
        assert "test_task" in registry.list_task_types()

    def test_register_duplicate_raises_error(self) -> None:
        """Test that registering duplicate task type raises error."""
        registry = TaskRegistry()

        def handler1(x: int) -> int:
            return x

        def handler2(x: int) -> int:
            return x * 2

        registry.register("duplicate_task", handler1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register("duplicate_task", handler2)

    def test_get_handler(self) -> None:
        """Test retrieving a registered handler."""
        registry = TaskRegistry()

        def my_handler(value: int) -> int:
            return value * 2

        registry.register("multiply", my_handler)

        handler = registry.get_handler("multiply")
        assert handler is not None
        assert handler(5) == 10

    def test_get_nonexistent_handler(self) -> None:
        """Test getting handler for non-registered task type."""
        registry = TaskRegistry()

        handler = registry.get_handler("nonexistent")
        assert handler is None

    def test_list_task_types(self) -> None:
        """Test listing all registered task types."""
        registry = TaskRegistry()

        def handler1(x: int) -> int:
            return x

        def handler2(x: str) -> str:
            return x.upper()

        registry.register("task1", handler1)
        registry.register("task2", handler2)

        task_types = registry.list_task_types()
        assert len(task_types) == 2
        assert "task1" in task_types
        assert "task2" in task_types

    def test_is_registered(self) -> None:
        """Test checking if task type is registered."""
        registry = TaskRegistry()

        def handler(x: int) -> int:
            return x

        registry.register("test_task", handler)

        assert registry.is_registered("test_task")
        assert not registry.is_registered("other_task")

    def test_unregister_handler(self) -> None:
        """Test unregistering a task handler."""
        registry = TaskRegistry()

        def handler(x: int) -> int:
            return x

        registry.register("temp_task", handler)
        assert registry.is_registered("temp_task")

        result = registry.unregister("temp_task")
        assert result is True
        assert not registry.is_registered("temp_task")

    def test_unregister_nonexistent_handler(self) -> None:
        """Test unregistering a non-existent handler."""
        registry = TaskRegistry()

        result = registry.unregister("nonexistent")
        assert result is False
