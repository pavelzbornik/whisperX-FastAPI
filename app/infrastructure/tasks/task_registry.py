"""Task registry for mapping task types to handler functions."""

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class TaskRegistry:
    """
    Registry of available background task handlers.

    This class maintains a mapping of task type identifiers to their
    corresponding handler functions. It provides a centralized way to
    register and retrieve task handlers for the task executor.

    The registry follows the Strategy Pattern, allowing different handlers
    to be registered for different task types without modifying the
    execution logic.

    Example:
        >>> registry = TaskRegistry()
        >>> registry.register("audio_processing", process_audio_handler)
        >>> handler = registry.get_handler("audio_processing")
        >>> result = handler(audio_path="/tmp/audio.mp3")

    Thread Safety:
        This class is not thread-safe. In a multi-threaded environment,
        registration should happen during application startup before
        concurrent access.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._handlers: dict[str, Callable[..., Any]] = {}
        logger.info("TaskRegistry initialized")

    def register(self, task_type: str, handler: Callable[..., Any]) -> None:
        """
        Register a task handler.

        Args:
            task_type: Unique task type identifier (e.g., "audio_processing")
            handler: Callable that executes the task

        Raises:
            ValueError: If task type already registered

        Example:
            >>> def my_handler(param: str) -> dict:
            ...     return {"result": param}
            >>> registry.register("my_task", my_handler)
        """
        if task_type in self._handlers:
            raise ValueError(f"Task type '{task_type}' already registered")

        self._handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")

    def get_handler(self, task_type: str) -> Callable[..., Any] | None:
        """
        Get handler for task type.

        Args:
            task_type: Task type identifier

        Returns:
            Handler callable if found, None otherwise

        Example:
            >>> handler = registry.get_handler("audio_processing")
            >>> if handler:
            ...     result = handler(audio_path="/tmp/audio.mp3")
        """
        handler = self._handlers.get(task_type)
        if not handler:
            logger.warning(f"No handler registered for task type: {task_type}")
        return handler

    def list_task_types(self) -> list[str]:
        """
        List all registered task types.

        Returns:
            List of registered task type identifiers

        Example:
            >>> types = registry.list_task_types()
            >>> print(f"Registered types: {types}")
        """
        return list(self._handlers.keys())

    def is_registered(self, task_type: str) -> bool:
        """
        Check if a task type is registered.

        Args:
            task_type: Task type identifier

        Returns:
            True if registered, False otherwise

        Example:
            >>> if registry.is_registered("audio_processing"):
            ...     print("Handler is registered")
        """
        return task_type in self._handlers

    def unregister(self, task_type: str) -> bool:
        """
        Unregister a task handler.

        Args:
            task_type: Task type identifier

        Returns:
            True if handler was removed, False if not found

        Example:
            >>> registry.unregister("audio_processing")
        """
        if task_type in self._handlers:
            del self._handlers[task_type]
            logger.info(f"Unregistered handler for task type: {task_type}")
            return True
        return False
