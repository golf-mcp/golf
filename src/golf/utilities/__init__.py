"""Golf utilities for enhanced MCP tool development.

This module provides convenient utilities for Golf tool authors to access
advanced MCP features like elicitation and sampling without needing to 
manage FastMCP Context objects directly.
"""

from .elicitation import elicit
from .sampling import sample
from .context import get_current_context

__all__ = ["elicit", "sample", "get_current_context"]