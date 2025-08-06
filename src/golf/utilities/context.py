"""Context utilities for Golf MCP tools.

This module provides utilities to access the current FastMCP Context
from within Golf tool functions.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp.server.context import Context


def get_current_context() -> "Context":
    """Get the current FastMCP Context.

    This function retrieves the current FastMCP Context that was injected
    into the tool function. It works by importing the FastMCP context
    utilities at runtime.

    Returns:
        The current FastMCP Context instance

    Raises:
        RuntimeError: If called outside of an MCP request context
        ImportError: If FastMCP is not available

    Example:
        ```python
        from golf.utilities import get_current_context

        async def my_tool(data: str):
            ctx = get_current_context()
            await ctx.info(f"Processing: {data}")
            return "done"
        ```
    """
    try:
        # Import FastMCP context utilities at runtime
        from fastmcp.server.context import _current_context

        # Get the current context from the context variable
        context = _current_context.get(None)

        if context is None:
            raise RuntimeError(
                "No FastMCP Context available. This function must be called "
                "from within an MCP tool function that has context injection enabled."
            )

        return context

    except ImportError as e:
        raise ImportError("FastMCP is not available. Please ensure fastmcp>=2.11.0 is installed.") from e
