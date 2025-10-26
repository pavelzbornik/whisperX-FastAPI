"""Structured logging with OpenTelemetry trace context integration."""

import logging

from opentelemetry import trace


class TraceContextFilter(logging.Filter):
    """
    Logging filter that adds trace context to log records.

    This filter extracts the trace_id and span_id from the current active span
    and adds them as attributes to log records, enabling correlation between
    logs and traces.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add trace_id and span_id to log record.

        Args:
            record: The log record to augment with trace context.

        Returns:
            Always returns True to allow the record to be logged.
        """
        span = trace.get_current_span()

        if span.is_recording():
            ctx = span.get_span_context()
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            # Use zero values when no active span
            record.trace_id = "0" * 32
            record.span_id = "0" * 16

        return True


def configure_logging_with_traces() -> None:
    """
    Configure logging to include trace context.

    This function adds the TraceContextFilter to all loggers in the application,
    enabling automatic correlation between logs and traces.
    """
    # Add trace context filter to root logger
    root_logger = logging.getLogger()
    trace_filter = TraceContextFilter()
    root_logger.addFilter(trace_filter)

    # Also add to app logger
    app_logger = logging.getLogger("app")
    app_logger.addFilter(trace_filter)

    # Update formatter to include trace context
    # Note: This assumes formatters have been configured elsewhere
    # Format string should include %(trace_id)s and %(span_id)s
