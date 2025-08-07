"""Golf utilities for enhanced MCP tool development.

This module provides convenient utilities for Golf tool authors to access
advanced MCP features like elicitation and sampling without needing to
manage FastMCP Context objects directly.
"""

from .elicitation import elicit, elicit_confirmation
from .sampling import sample, sample_structured, sample_with_context
from .context import get_current_context

__all__ = ["elicit", "elicit_confirmation", "sample", "sample_structured", "sample_with_context", "get_current_context"]
