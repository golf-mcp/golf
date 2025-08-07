"""Elicitation utilities for Golf MCP tools.

This module provides simplified elicitation functions that Golf tool authors
can use without needing to manage FastMCP Context objects directly.
"""

from typing import Any, TypeVar, overload
from collections.abc import Callable

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
    response_type: None = None,
) -> dict[str, Any]:
    """Elicit with no response type returns empty dict."""
    ...


@overload
async def elicit(
    message: str,
    response_type: type[T],
) -> T:
    """Elicit with response type returns typed data."""
    ...


@overload
async def elicit(
    message: str,
    response_type: list[str],
) -> str:
    """Elicit with list of options returns selected string."""
    ...


async def elicit(
    message: str,
    response_type: type[T] | list[str] | None = None,
) -> T | dict[str, Any] | str:
    """Request additional information from the user via MCP elicitation.

    This is a simplified wrapper around FastMCP's Context.elicit() method
    that automatically handles context retrieval and response processing.

    Args:
        message: Human-readable message explaining what information is needed
        response_type: The type of response expected:
            - None: Returns empty dict (for confirmation prompts)
            - type[T]: Returns validated instance of T (BaseModel, dataclass, etc.)
            - list[str]: Returns selected string from the options

    Returns:
        The user's response in the requested format

    Raises:
        RuntimeError: If called outside MCP context or user declines/cancels
        ValueError: If response validation fails

    Examples:
        ```python
        from golf.utilities import elicit
        from pydantic import BaseModel

        class UserInfo(BaseModel):
            name: str
            email: str

        async def collect_user_info():
            # Structured elicitation
            info = await elicit("Please provide your details:", UserInfo)

            # Simple text elicitation
            reason = await elicit("Why do you need this?", str)

            # Multiple choice elicitation
            priority = await elicit("Select priority:", ["low", "medium", "high"])

            # Confirmation elicitation
            await elicit("Proceed with the action?")

            return f"User {info.name} requested {reason} with {priority} priority"
        ```
    """
    try:
        # Get the current FastMCP context
        ctx = get_current_context()

        # Call the context's elicit method
        result = await ctx.elicit(message, response_type)

        # Handle the response based on the action
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


async def elicit_confirmation(message: str) -> bool:
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

        async def delete_file(filename: str):
            confirmed = await elicit_confirmation(
                f"Are you sure you want to delete {filename}?"
            )
            if confirmed:
                # Proceed with deletion
                return f"Deleted {filename}"
            else:
                return "Deletion cancelled"
        ```
    """
    try:
        # Use elicitation with boolean choice
        choice = await elicit(message, ["yes", "no"])
        return choice.lower() == "yes"
    except RuntimeError as e:
        if "declined" in str(e):
            return False
        raise  # Re-raise cancellation or other errors


# Apply instrumentation to all elicitation functions
elicit = instrument_elicitation(elicit, "elicit")
elicit_confirmation = instrument_elicitation(elicit_confirmation, "confirmation")
