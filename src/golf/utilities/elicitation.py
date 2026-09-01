"""Elicitation helpers for legacy and MCP 2026-07-28 connections."""

import hashlib
import json
from collections.abc import Callable
from typing import Any, TypeVar, overload

from fastmcp.server.elicitation import (
    handle_elicit_accept,
    parse_elicit_response_type,
)
from mcp_types import ElicitRequest, ElicitRequestFormParams, ElicitResult, InputRequiredResult
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

from .context import get_current_context

T = TypeVar("T")

# Apply telemetry instrumentation if available
try:
    from golf.telemetry import instrument_elicitation

    _instrumentation_available = True
except ImportError:
    _instrumentation_available = False

    def instrument_elicitation(func: Callable, elicitation_type: str = "elicit") -> Callable:
        """No-op instrumentation when telemetry is not available."""
        return func


@overload
async def elicit(
    message: str,
    response_type: type[T],
) -> T | InputRequiredResult:
    """Elicit with response type returns typed data."""
    ...


@overload
async def elicit(
    message: str,
    response_type: list[str],
) -> str | InputRequiredResult:
    """Elicit with list of options returns selected string."""
    ...


async def elicit(
    message: str,
    response_type: type[T] | list[str],
    *,
    request_key: str | None = None,
) -> T | str | InputRequiredResult:
    """Request additional information from the user via MCP elicitation.

    Legacy connections use imperative ``ctx.elicit``. MCP 2026-07-28 uses the
    MRTR guard pattern: the first call returns ``InputRequiredResult`` and the
    containing tool must return it unchanged. FastMCP re-runs the tool with the
    answer available through ``ctx.input_responses``.

    Args:
        message: Human-readable message explaining what information is needed
        response_type: The type of response expected:
            - type[T]: Returns validated instance of T (BaseModel, dataclass, etc.)
            - list[str]: Returns selected string from the options
        request_key: Stable key for this question. By default a deterministic
            key is derived from the rendered request.

    Returns:
        The user's response in the requested format

    Raises:
        RuntimeError: If called outside MCP context or user declines/cancels
        ValueError: If response validation fails

    Examples:
        ```python
        from golf.utilities import elicit
        from mcp_types import InputRequiredResult
        from pydantic import BaseModel

        class UserInfo(BaseModel):
            name: str
            email: str

        async def collect_user_info():
            # Structured elicitation
            info = await elicit("Please provide your details:", UserInfo)
            if isinstance(info, InputRequiredResult):
                return info

            # Simple text elicitation
            reason = await elicit("Why do you need this?", str)
            if isinstance(reason, InputRequiredResult):
                return reason

            # Multiple choice elicitation
            priority = await elicit("Select priority:", ["low", "medium", "high"])
            if isinstance(priority, InputRequiredResult):
                return priority

            # Confirmation elicitation
            confirmed = await elicit("Proceed with the action?", bool)
            if isinstance(confirmed, InputRequiredResult):
                return confirmed

            return f"User {info.name} requested {reason} with {priority} priority"
        ```
    """
    try:
        ctx = get_current_context()
        config = parse_elicit_response_type(response_type)

        request_context = ctx.request_context
        protocol_version = request_context.protocol_version if request_context is not None else None
        if protocol_version in MODERN_PROTOCOL_VERSIONS:
            params = ElicitRequestFormParams(
                message=message,
                requested_schema=config.schema,
            )
            key = request_key or _request_key(params)
            response = (ctx.input_responses or {}).get(key)
            if response is None:
                return InputRequiredResult(input_requests={key: ElicitRequest(params=params)})
            if not isinstance(response, ElicitResult):
                raise RuntimeError(f"Elicitation response {key!r} was not an ElicitResult")
            result = response
            if result.action == "accept":
                return handle_elicit_accept(config, result.content).data
        else:
            result = await ctx.elicit(message, response_type)

        if hasattr(result, "action"):
            if result.action == "accept":
                return result.data
            elif result.action == "decline":
                raise RuntimeError(f"User declined the elicitation request: {message}")
            elif result.action == "cancel":
                raise RuntimeError(f"User cancelled the elicitation request: {message}")
            else:
                raise RuntimeError(f"Unexpected elicitation response: {result.action}")
        else:
            # Direct response (shouldn't happen with current FastMCP)
            return result

    except Exception as e:
        if isinstance(e, RuntimeError):
            raise  # Re-raise our custom errors
        raise RuntimeError(f"Elicitation failed: {str(e)}") from e


def _request_key(params: ElicitRequestFormParams) -> str:
    payload = params.model_dump(mode="json", by_alias=True, exclude_none=True)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    return f"golf.elicit.{digest}"


async def elicit_confirmation(message: str) -> bool | InputRequiredResult:
    """Request a simple yes/no confirmation from the user.

    This is a convenience function for common confirmation prompts.

    Args:
        message: The confirmation message to show the user

    Returns:
        True if user confirmed, False if declined

    Raises:
        RuntimeError: If user cancels or other error occurs

    Example:
        ```python
        from golf.utilities import elicit_confirmation
        from mcp_types import InputRequiredResult

        async def delete_file(filename: str) -> str | InputRequiredResult:
            confirmed = await elicit_confirmation(
                f"Are you sure you want to delete {filename}?"
            )
            if isinstance(confirmed, InputRequiredResult):
                return confirmed
            if confirmed:
                # Proceed with deletion
                return f"Deleted {filename}"
            else:
                return "Deletion cancelled"
        ```
    """
    try:
        result = await elicit(message, bool)
        if isinstance(result, InputRequiredResult):
            return result
        return result
    except RuntimeError as e:
        if "declined" in str(e):
            return False
        raise  # Re-raise cancellation or other errors


# Apply instrumentation to all elicitation functions
elicit = instrument_elicitation(elicit, "elicit")
elicit_confirmation = instrument_elicitation(elicit_confirmation, "confirmation")
