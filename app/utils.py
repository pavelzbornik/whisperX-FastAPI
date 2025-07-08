"""Utility functions for the whisperX FastAPI application."""

from datetime import datetime, timezone
from typing import Any, Dict


def utc_now() -> datetime:
    """
    Get current UTC datetime with timezone awareness.
    
    Replaces deprecated datetime.utcnow() with timezone-aware alternative.
    
    Returns:
        datetime: Current UTC datetime with timezone info
    """
    return datetime.now(timezone.utc)


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize data for logging by masking sensitive information.
    
    Args:
        data: Dictionary containing data to be logged
        
    Returns:
        Dictionary with sensitive data masked
    """
    sensitive_keys = {'token', 'password', 'secret', 'key', 'auth', 'credential'}
    
    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            if isinstance(value, str) and len(value) > 4:
                sanitized[key] = f"{value[:2]}***{value[-2:]}"
            else:
                sanitized[key] = "***"
        else:
            sanitized[key] = value
    
    return sanitized


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"