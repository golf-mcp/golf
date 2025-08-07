"""Golf telemetry module for OpenTelemetry instrumentation."""

from golf.telemetry.instrumentation import (
    get_tracer,
    init_telemetry,
    instrument_elicitation,
    instrument_prompt,
    instrument_resource,
    instrument_sampling,
    instrument_tool,
    telemetry_lifespan,
)

__all__ = [
    "instrument_tool",
    "instrument_resource",
    "instrument_prompt",
    "instrument_elicitation",
    "instrument_sampling",
    "telemetry_lifespan",
    "init_telemetry",
    "get_tracer",
]
