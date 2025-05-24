"""Golf telemetry module for OpenTelemetry instrumentation."""

from golf.telemetry.instrumentation import (
    instrument_tool,
    instrument_resource,
    instrument_prompt,
    telemetry_lifespan,
    init_telemetry,
    get_tracer,
)

__all__ = [
    "instrument_tool",
    "instrument_resource", 
    "instrument_prompt",
    "telemetry_lifespan",
    "init_telemetry",
    "get_tracer",
] 