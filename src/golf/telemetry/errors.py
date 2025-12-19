"""Utility functions for recording runtime errors to OpenTelemetry traces."""

from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


def record_http_error(
    status_code: int,
    method: str,
    path: str,
    operation: str = "http_request",
    component: str = "golf",
    error_message: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Record an HTTP error response to the current trace span.

    This function safely records HTTP errors (non-200/202 responses) to the current
    OpenTelemetry span. Use this for capturing failed OAuth flows, health check
    failures, or any other HTTP endpoint that returns an error status.

    Args:
        status_code: The HTTP status code (e.g., 401, 403, 500, 503)
        method: HTTP method (GET, POST, etc.)
        path: Request path (e.g., "/oauth/token", "/health")
        operation: Name of the operation (e.g., "oauth_token", "health_check")
        component: Source component (default: "golf")
        error_message: Optional error message to include
        attributes: Optional additional attributes to add to the span

    Example:
        if response.status_code == 401:
            record_http_error(401, "POST", "/oauth/token", "oauth_token",
                              error_message="Invalid credentials")
    """
    span = trace.get_current_span()

    # Safety check: no span or span not recording
    if span is None or not span.is_recording():
        return

    # Only record errors for 4xx and 5xx status codes
    if status_code < 400:
        return

    # Determine error category
    error_category = "client_error" if status_code < 500 else "server_error"

    # Build event attributes
    event_attrs: dict[str, Any] = {
        "http.status_code": status_code,
        "http.method": method,
        "http.path": path,
        "error.category": error_category,
        "error.source": component,
        "operation": operation,
    }

    if error_message:
        event_attrs["error.message"] = error_message

    if attributes:
        event_attrs.update({f"error.{k}": str(v) for k, v in attributes.items()})

    # Set span status to ERROR
    status_description = f"{component}.{operation}: HTTP {status_code}"
    if error_message:
        status_description += f" - {error_message}"
    span.set_status(Status(StatusCode.ERROR, status_description))

    # Add HTTP status code attribute
    span.set_attribute("http.status_code", status_code)

    # Add an error event with structured attributes
    span.add_event(f"{component}.http_error", event_attrs)


def record_runtime_error(
    error: Exception,
    operation: str,
    component: str = "golf",
    attributes: dict[str, Any] | None = None,
) -> None:
    """Record a runtime error to the current trace span.

    This function safely records an error to the current OpenTelemetry span,
    if one exists and is recording. It's designed to be called from generated
    server code or extension libraries like golf-mcp-enterprise.

    Args:
        error: The exception that occurred
        operation: Name of the operation that failed (e.g., "startup_script", "health_check")
        component: Source component (default: "golf", could be "golf-mcp-enterprise")
        attributes: Optional additional attributes to add to the span

    Example:
        try:
            run_startup_script()
        except Exception as e:
            record_runtime_error(e, "startup_script")
            print(f"Startup failed: {e}", file=sys.stderr)
    """
    span = trace.get_current_span()

    # Safety check: no span or span not recording
    if span is None or not span.is_recording():
        return

    # Record the exception with escaped=True since we're not suppressing it
    extra_attrs = {
        "error.source": component,
        "error.operation": operation,
    }
    if attributes:
        extra_attrs.update({f"error.{k}": str(v) for k, v in attributes.items()})

    span.record_exception(error, attributes=extra_attrs, escaped=True)

    # Set span status to ERROR
    span.set_status(
        Status(StatusCode.ERROR, f"{component}.{operation}: {type(error).__name__}: {error}")
    )

    # Add an error event with structured attributes
    span.add_event(
        f"{component}.runtime_error",
        {
            "operation": operation,
            "error.type": type(error).__name__,
            "error.message": str(error),
        },
    )
