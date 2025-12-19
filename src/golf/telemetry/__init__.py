"""Golf telemetry module for OpenTelemetry instrumentation."""

from golf.telemetry.instrumentation import (
    get_provider,
    get_tracer,
    init_telemetry,
    instrument_elicitation,
    instrument_prompt,
    instrument_resource,
    instrument_sampling,
    instrument_tool,
    telemetry_lifespan,
    OpenTelemetryMiddleware,
    OTelContextCapturingMiddleware,
)
from golf.telemetry.errors import record_http_error, record_runtime_error

__all__ = [
    "instrument_tool",
    "instrument_resource",
    "instrument_prompt",
    "instrument_elicitation",
    "instrument_sampling",
    "telemetry_lifespan",
    "init_telemetry",
    "get_provider",
    "get_tracer",
    "OpenTelemetryMiddleware",
    "OTelContextCapturingMiddleware",
    "record_http_error",
    "record_runtime_error",
]
