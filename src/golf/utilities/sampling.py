"""Sampling utilities for Golf MCP tools.

This module provides simplified LLM sampling functions that Golf tool authors
can use without needing to manage FastMCP Context objects directly.
"""

from typing import Any
from collections.abc import Callable

from .context import get_current_context

# Apply telemetry instrumentation if available
try:
    from golf.telemetry import instrument_sampling

    _instrumentation_available = True
except ImportError:
    _instrumentation_available = False

    def instrument_sampling(func: Callable, sampling_type: str = "sample") -> Callable:
        """No-op instrumentation when telemetry is not available."""
        return func


async def sample(
    messages: str | list[str],
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model_preferences: str | list[str] | None = None,
) -> str:
    """Request an LLM completion from the MCP client.

    This is a simplified wrapper around FastMCP's Context.sample() method
    that automatically handles context retrieval and response processing.

    Args:
        messages: The message(s) to send to the LLM:
            - str: Single user message
            - list[str]: Multiple user messages
        system_prompt: Optional system prompt to guide the LLM
        temperature: Optional temperature for sampling (0.0 to 1.0)
        max_tokens: Optional maximum tokens to generate (default: 512)
        model_preferences: Optional model preferences:
            - str: Single model name hint
            - list[str]: Multiple model name hints in preference order

    Returns:
        The LLM's response as a string

    Raises:
        RuntimeError: If called outside MCP context or sampling fails
        ValueError: If parameters are invalid

    Examples:
        ```python
        from golf.utilities import sample

        async def analyze_data(data: str):
            # Simple completion
            analysis = await sample(f"Analyze this data: {data}")

            # With system prompt and temperature
            creative_response = await sample(
                "Write a creative story about this data",
                system_prompt="You are a creative writer",
                temperature=0.8,
                max_tokens=1000
            )

            # With model preferences
            technical_analysis = await sample(
                f"Provide technical analysis: {data}",
                model_preferences=["gpt-4", "claude-3-sonnet"]
            )

            return {
                "analysis": analysis,
                "creative": creative_response,
                "technical": technical_analysis
            }
        ```
    """
    try:
        # Get the current FastMCP context
        ctx = get_current_context()

        # Call the context's sample method
        result = await ctx.sample(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model_preferences=model_preferences,
        )

        # Extract text content from the ContentBlock response
        if hasattr(result, "text"):
            return result.text
        elif hasattr(result, "content"):
            # Handle different content block types
            if isinstance(result.content, str):
                return result.content
            elif hasattr(result.content, "text"):
                return result.content.text
            else:
                return str(result.content)
        else:
            return str(result)

    except Exception as e:
        raise RuntimeError(f"LLM sampling failed: {str(e)}") from e


async def sample_structured(
    messages: str | list[str],
    format_instructions: str,
    system_prompt: str | None = None,
    temperature: float = 0.1,
    max_tokens: int | None = None,
) -> str:
    """Request a structured LLM completion with specific formatting.

    This is a convenience function for requesting structured responses
    like JSON, XML, or other formatted output.

    Args:
        messages: The message(s) to send to the LLM
        format_instructions: Instructions for the desired output format
        system_prompt: Optional system prompt
        temperature: Temperature for sampling (default: 0.1 for consistency)
        max_tokens: Optional maximum tokens to generate

    Returns:
        The structured LLM response as a string

    Example:
        ```python
        from golf.utilities import sample_structured

        async def extract_entities(text: str):
            entities = await sample_structured(
                f"Extract entities from: {text}",
                format_instructions="Return as JSON with keys: persons, "
                "organizations, locations",
                system_prompt="You are an expert at named entity recognition"
            )
            return entities
        ```
    """
    # Combine the format instructions with the messages
    if isinstance(messages, str):
        formatted_message = f"{messages}\n\n{format_instructions}"
    else:
        formatted_message = messages + [format_instructions]

    return await sample(
        messages=formatted_message,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def sample_with_context(
    messages: str | list[str],
    context_data: dict[str, Any],
    system_prompt: str | None = None,
    **kwargs: Any,
) -> str:
    """Request an LLM completion with additional context data.

    This convenience function formats context data and includes it
    in the sampling request.

    Args:
        messages: The message(s) to send to the LLM
        context_data: Dictionary of context data to include
        system_prompt: Optional system prompt
        **kwargs: Additional arguments passed to sample()

    Returns:
        The LLM response as a string

    Example:
        ```python
        from golf.utilities import sample_with_context

        async def generate_report(topic: str, user_data: dict):
            report = await sample_with_context(
                f"Generate a report about {topic}",
                context_data={
                    "user_preferences": user_data,
                    "timestamp": "2024-01-01",
                    "format": "markdown"
                },
                system_prompt="You are a professional report writer"
            )
            return report
        ```
    """
    # Format context data as a readable string
    context_str = "\n".join([f"{k}: {v}" for k, v in context_data.items()])

    # Add context to the message
    if isinstance(messages, str):
        contextual_message = f"{messages}\n\nContext:\n{context_str}"
    else:
        contextual_message = messages + [f"Context:\n{context_str}"]

    return await sample(
        messages=contextual_message,
        system_prompt=system_prompt,
        **kwargs,
    )


# Apply instrumentation to all sampling functions
sample = instrument_sampling(sample, "sample")
sample_structured = instrument_sampling(sample_structured, "structured")
sample_with_context = instrument_sampling(sample_with_context, "context")
