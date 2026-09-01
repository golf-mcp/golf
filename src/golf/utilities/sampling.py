"""Sampling helpers for legacy and MCP 2026-07-28 connections.

Modern MCP sampling is caller-owned multi-round-trip (MRTR) control flow. A
tool must return the ``InputRequiredResult`` produced by these helpers and will
be invoked again with the answer in ``Context.input_responses``.
"""

import hashlib
import json
from collections.abc import Callable
from typing import Any

from mcp_types import (
    CreateMessageRequest,
    CreateMessageRequestParams,
    CreateMessageResult,
    InputRequiredResult,
    ModelHint,
    ModelPreferences,
    SamplingMessage,
    TextContent,
)
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

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
    *,
    request_key: str | None = None,
) -> str | InputRequiredResult:
    """Request an LLM completion from the MCP client.

    On legacy connections this sends the imperative server-to-client sampling
    request and returns text. On MCP 2026-07-28 it returns an
    ``InputRequiredResult`` on the first leg. The containing tool must return
    that value unchanged; on the next leg this helper reads
    ``ctx.input_responses`` and returns text.

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
        RuntimeError: If sampling fails or a modern response is invalid
        ValueError: If parameters are invalid

    Examples:
        ```python
        from golf.utilities import sample
        from mcp_types import InputRequiredResult

        async def analyze_data(data: str):
            # Simple completion
            analysis = await sample(f"Analyze this data: {data}")
            if isinstance(analysis, InputRequiredResult):
                return analysis

            # With system prompt and temperature
            creative_response = await sample(
                "Write a creative story about this data",
                system_prompt="You are a creative writer",
                temperature=0.8,
                max_tokens=1000
            )
            if isinstance(creative_response, InputRequiredResult):
                return creative_response

            # With model preferences
            technical_analysis = await sample(
                f"Provide technical analysis: {data}",
                model_preferences=["gpt-4", "claude-3-sonnet"]
            )
            if isinstance(technical_analysis, InputRequiredResult):
                return technical_analysis

            return {
                "analysis": analysis,
                "creative": creative_response,
                "technical": technical_analysis
            }
        ```
    """
    try:
        ctx = get_current_context()
        sampling_messages = [
            SamplingMessage(role="user", content=TextContent(type="text", text=message))
            for message in ([messages] if isinstance(messages, str) else messages)
        ]
        preferences = _model_preferences(model_preferences)
        params = CreateMessageRequestParams(
            messages=sampling_messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens or 512,
            model_preferences=preferences,
        )

        request_context = ctx.request_context
        protocol_version = request_context.protocol_version if request_context is not None else None
        if protocol_version in MODERN_PROTOCOL_VERSIONS:
            key = request_key or _request_key("sample", params)
            responses = ctx.input_responses or {}
            response = responses.get(key)
            if response is None:
                return InputRequiredResult(input_requests={key: CreateMessageRequest(params=params)})
            if not isinstance(response, CreateMessageResult):
                raise RuntimeError(f"Sampling response {key!r} was not a CreateMessageResult")
            return _response_text(response)

        result = await ctx.session.create_message(
            messages=sampling_messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens or 512,
            model_preferences=preferences,
            related_request_id=ctx.request_id,
        )
        return _response_text(result)

    except Exception as e:
        raise RuntimeError(f"LLM sampling failed: {str(e)}") from e


def _model_preferences(
    preferences: str | list[str] | None,
) -> ModelPreferences | None:
    if preferences is None:
        return None
    names = [preferences] if isinstance(preferences, str) else preferences
    return ModelPreferences(hints=[ModelHint(name=name) for name in names])


def _request_key(prefix: str, params: CreateMessageRequestParams) -> str:
    payload = params.model_dump(mode="json", by_alias=True, exclude_none=True)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    return f"golf.{prefix}.{digest}"


def _response_text(result: CreateMessageResult) -> str:
    content = result.content
    if isinstance(content, list):
        return "\n".join(block.text for block in content if isinstance(block, TextContent))
    if isinstance(content, TextContent):
        return content.text
    raise RuntimeError("Sampling response did not contain text content")


async def sample_structured(
    messages: str | list[str],
    format_instructions: str,
    system_prompt: str | None = None,
    temperature: float = 0.1,
    max_tokens: int | None = None,
) -> str | InputRequiredResult:
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
        from mcp_types import InputRequiredResult

        async def extract_entities(text: str):
            entities = await sample_structured(
                f"Extract entities from: {text}",
                format_instructions="Return as JSON with keys: persons, "
                "organizations, locations",
                system_prompt="You are an expert at named entity recognition"
            )
            if isinstance(entities, InputRequiredResult):
                return entities
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
) -> str | InputRequiredResult:
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
        from mcp_types import InputRequiredResult

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
            if isinstance(report, InputRequiredResult):
                return report
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
