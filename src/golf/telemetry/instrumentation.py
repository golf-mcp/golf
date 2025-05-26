"""Component-level OpenTelemetry instrumentation for Golf-built servers."""

import os
import sys
import functools
from typing import Callable, Optional, TypeVar
from contextlib import asynccontextmanager
import asyncio

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry import baggage

T = TypeVar('T')

# Global tracer instance
_tracer: Optional[trace.Tracer] = None
_provider: Optional[TracerProvider] = None
_instrumented_tools = []

def init_telemetry(service_name: str = "golf-mcp-server") -> Optional[TracerProvider]:
    """Initialize OpenTelemetry with environment-based configuration.
    
    Returns None if required environment variables are not set.
    """
    global _provider
    
    # Check for required environment variables based on exporter type
    exporter_type = os.environ.get("OTEL_TRACES_EXPORTER", "console").lower()
    
    # For OTLP HTTP exporter, check if endpoint is configured
    if exporter_type == "otlp_http":
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint:
            print(f"[WARNING] OpenTelemetry tracing is disabled: OTEL_EXPORTER_OTLP_ENDPOINT is not set for OTLP HTTP exporter")
            return None
    
    # Create resource with service information
    resource_attributes = {
        "service.name": os.environ.get("OTEL_SERVICE_NAME", service_name),
        "service.version": os.environ.get("SERVICE_VERSION", "1.0.0"),
        "service.instance.id": os.environ.get("SERVICE_INSTANCE_ID", "default"),
    }
    resource = Resource.create(resource_attributes)
    
    # Create provider
    provider = TracerProvider(resource=resource)
    
    # Configure exporter based on type
    try:
        if exporter_type == "otlp_http":
            endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
            headers = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
            
            # Parse headers if provided
            header_dict = {}
            if headers:
                for header in headers.split(","):
                    if "=" in header:
                        key, value = header.split("=", 1)
                        header_dict[key.strip()] = value.strip()
            
            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers=header_dict if header_dict else None
            )
        else:
            # Default to console exporter
            exporter = ConsoleSpanExporter(out=sys.stderr)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise
    
    # Add batch processor for better performance
    try:
        processor = BatchSpanProcessor(
            exporter,
            max_queue_size=2048,
            schedule_delay_millis=1000,  # Export every 1 second instead of default 5 seconds
            max_export_batch_size=512,
            export_timeout_millis=5000
        )
        provider.add_span_processor(processor)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise
    
    # Set as global provider
    try:
        # Check if a provider is already set to avoid the warning
        existing_provider = trace.get_tracer_provider()
        if existing_provider is None or str(type(existing_provider).__name__) == 'ProxyTracerProvider':
            # Only set if no provider exists or it's the default proxy provider
            trace.set_tracer_provider(provider)
        _provider = provider
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise
    
    # Create a test span to verify everything is working
    try:
        test_tracer = provider.get_tracer("golf.telemetry.test", "1.0.0")
        with test_tracer.start_as_current_span("startup.test") as span:
            span.set_attribute("test", True)
            span.set_attribute("service.name", service_name)
            span.set_attribute("exporter.type", exporter_type)
            span.set_attribute("endpoint", os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "not set"))
    except Exception as e:
        import traceback
        traceback.print_exc()
    
    return provider

def get_tracer() -> trace.Tracer:
    """Get or create the global tracer instance."""
    global _tracer, _provider
    
    # If no provider is set, telemetry is disabled - return no-op tracer
    if _provider is None:
        return trace.get_tracer("golf.mcp.components.noop", "1.0.0")
    
    if _tracer is None:
        _tracer = trace.get_tracer("golf.mcp.components", "1.0.0")
    return _tracer

def _add_component_attributes(span: Span, component_type: str, component_name: str, **kwargs):
    """Add standard component attributes to a span."""
    span.set_attribute("mcp.component.type", component_type)
    span.set_attribute("mcp.component.name", component_name)
    
    # Add any additional attributes
    for key, value in kwargs.items():
        if value is not None:
            span.set_attribute(f"mcp.component.{key}", str(value))

def instrument_tool(func: Callable[..., T], tool_name: str) -> Callable[..., T]:
    """Instrument a tool function with OpenTelemetry tracing."""
    global _provider
    
    # If telemetry is disabled, return the original function
    if _provider is None:
        return func
    
    tracer = get_tracer()
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        # Create a more descriptive span name
        span_name = f"mcp.tool.{tool_name}.execute"
        span = tracer.start_span(span_name)
        
        # Activate the span in the current context
        from opentelemetry import context
        token = context.attach(trace.set_span_in_context(span))
        
        try:
            # Add comprehensive attributes
            span.set_attribute("mcp.component.type", "tool")
            span.set_attribute("mcp.component.name", tool_name)
            span.set_attribute("mcp.tool.name", tool_name)
            span.set_attribute("mcp.tool.function", func.__name__)
            span.set_attribute("mcp.tool.module", func.__module__ if hasattr(func, '__module__') else "unknown")
            
            # Add execution context
            span.set_attribute("mcp.execution.args_count", len(args))
            span.set_attribute("mcp.execution.kwargs_count", len(kwargs))
            span.set_attribute("mcp.execution.async", True)
            
            # Extract Context parameter if present - this should have MCP session info
            ctx = kwargs.get('ctx')
            if ctx:
                if hasattr(ctx, 'request_id'):
                    span.set_attribute("mcp.request.id", ctx.request_id)
                if hasattr(ctx, 'session_id'):
                    span.set_attribute("mcp.session.id", ctx.session_id)
                if hasattr(ctx, 'client_id'):
                    span.set_attribute("mcp.client.id", ctx.client_id)
                # Try to find any session-related attributes
                for attr in dir(ctx):
                    if 'session' in attr.lower() and not attr.startswith('_'):
                        value = getattr(ctx, attr, None)
                        if value:
                            span.set_attribute(f"mcp.context.{attr}", str(value))
            
            # Also check baggage for session ID
            session_id_from_baggage = baggage.get_baggage("mcp.session.id")
            if session_id_from_baggage:
                span.set_attribute("mcp.session.id", session_id_from_baggage)
            
            # Add tool arguments as span attributes (be careful with sensitive data)
            for i, arg in enumerate(args):
                if isinstance(arg, (str, int, float, bool)) or arg is None:
                    span.set_attribute(f"mcp.tool.arg.{i}", str(arg))
                elif hasattr(arg, '__dict__'):
                    # For objects, just record the type
                    span.set_attribute(f"mcp.tool.arg.{i}.type", type(arg).__name__)
            
            # Add named arguments with better naming
            for key, value in kwargs.items():
                if key != 'ctx':
                    if value is None:
                        span.set_attribute(f"mcp.tool.input.{key}", "null")
                    elif isinstance(value, (str, int, float, bool)):
                        span.set_attribute(f"mcp.tool.input.{key}", str(value))
                    elif isinstance(value, (list, tuple)):
                        span.set_attribute(f"mcp.tool.input.{key}.count", len(value))
                        span.set_attribute(f"mcp.tool.input.{key}.type", "array")
                    elif isinstance(value, dict):
                        span.set_attribute(f"mcp.tool.input.{key}.count", len(value))
                        span.set_attribute(f"mcp.tool.input.{key}.type", "object")
                        if len(value) < 10:
                            span.set_attribute(f"mcp.tool.input.{key}.keys", ",".join(value.keys()))
                    else:
                        # For other types, at least record the type
                        span.set_attribute(f"mcp.tool.input.{key}.type", type(value).__name__)
            
            # Add event for tool execution start
            span.add_event("tool.execution.started", {
                "tool.name": tool_name,
                "timestamp": trace.time_ns()
            })
            
            try:
                result = await func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                
                # Add event for successful completion
                span.add_event("tool.execution.completed", {
                    "tool.name": tool_name,
                    "timestamp": trace.time_ns()
                })
                
                # Capture result metadata with better structure
                if result is not None:
                    if isinstance(result, (str, int, float, bool)):
                        span.set_attribute("mcp.tool.result.value", str(result))
                        span.set_attribute("mcp.tool.result.type", type(result).__name__)
                    elif isinstance(result, list):
                        span.set_attribute("mcp.tool.result.count", len(result))
                        span.set_attribute("mcp.tool.result.type", "array")
                    elif isinstance(result, dict):
                        span.set_attribute("mcp.tool.result.count", len(result))
                        span.set_attribute("mcp.tool.result.type", "object")
                        if len(result) < 10:
                            span.set_attribute("mcp.tool.result.keys", ",".join(result.keys()))
                    elif hasattr(result, '__len__'):
                        span.set_attribute("mcp.tool.result.length", len(result))
                    
                    # For any result, record its type
                    span.set_attribute("mcp.tool.result.class", type(result).__name__)
                
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                
                # Add event for error
                span.add_event("tool.execution.error", {
                    "tool.name": tool_name,
                    "error.type": type(e).__name__,
                    "error.message": str(e),
                    "timestamp": trace.time_ns()
                })
                raise
        finally:
            # End the span and detach context
            span.end()
            context.detach(token)
            
            # Force flush the provider to ensure spans are exported
            global _provider
            if _provider:
                try:
                    _provider.force_flush(timeout_millis=1000)
                except Exception as e:
                    pass
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        # Create a more descriptive span name
        span_name = f"mcp.tool.{tool_name}.execute"
        span = tracer.start_span(span_name)
        
        # Activate the span in the current context
        from opentelemetry import context
        token = context.attach(trace.set_span_in_context(span))
        
        try:
            # Add comprehensive attributes
            span.set_attribute("mcp.component.type", "tool")
            span.set_attribute("mcp.component.name", tool_name)
            span.set_attribute("mcp.tool.name", tool_name)
            span.set_attribute("mcp.tool.function", func.__name__)
            span.set_attribute("mcp.tool.module", func.__module__ if hasattr(func, '__module__') else "unknown")
            
            # Add execution context
            span.set_attribute("mcp.execution.args_count", len(args))
            span.set_attribute("mcp.execution.kwargs_count", len(kwargs))
            span.set_attribute("mcp.execution.async", False)
            
            # Extract Context parameter if present - this should have MCP session info
            ctx = kwargs.get('ctx')
            if ctx:
                if hasattr(ctx, 'request_id'):
                    span.set_attribute("mcp.request.id", ctx.request_id)
                if hasattr(ctx, 'session_id'):
                    span.set_attribute("mcp.session.id", ctx.session_id)
                if hasattr(ctx, 'client_id'):
                    span.set_attribute("mcp.client.id", ctx.client_id)
                # Try to find any session-related attributes
                for attr in dir(ctx):
                    if 'session' in attr.lower() and not attr.startswith('_'):
                        value = getattr(ctx, attr, None)
                        if value:
                            span.set_attribute(f"mcp.context.{attr}", str(value))
            
            # Also check baggage for session ID
            session_id_from_baggage = baggage.get_baggage("mcp.session.id")
            if session_id_from_baggage:
                span.set_attribute("mcp.session.id", session_id_from_baggage)
            
            # Add tool arguments as span attributes (be careful with sensitive data)
            for i, arg in enumerate(args):
                if isinstance(arg, (str, int, float, bool)) or arg is None:
                    span.set_attribute(f"mcp.tool.arg.{i}", str(arg))
                elif hasattr(arg, '__dict__'):
                    # For objects, just record the type
                    span.set_attribute(f"mcp.tool.arg.{i}.type", type(arg).__name__)
            
            # Add named arguments with better naming
            for key, value in kwargs.items():
                if key != 'ctx':
                    if value is None:
                        span.set_attribute(f"mcp.tool.input.{key}", "null")
                    elif isinstance(value, (str, int, float, bool)):
                        span.set_attribute(f"mcp.tool.input.{key}", str(value))
                    elif isinstance(value, (list, tuple)):
                        span.set_attribute(f"mcp.tool.input.{key}.count", len(value))
                        span.set_attribute(f"mcp.tool.input.{key}.type", "array")
                    elif isinstance(value, dict):
                        span.set_attribute(f"mcp.tool.input.{key}.count", len(value))
                        span.set_attribute(f"mcp.tool.input.{key}.type", "object")
                        if len(value) < 10:
                            span.set_attribute(f"mcp.tool.input.{key}.keys", ",".join(value.keys()))
                    else:
                        # For other types, at least record the type
                        span.set_attribute(f"mcp.tool.input.{key}.type", type(value).__name__)
            
            # Add event for tool execution start
            span.add_event("tool.execution.started", {
                "tool.name": tool_name,
                "timestamp": trace.time_ns()
            })
            
            try:
                result = func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                
                # Add event for successful completion
                span.add_event("tool.execution.completed", {
                    "tool.name": tool_name,
                    "timestamp": trace.time_ns()
                })
                
                # Capture result metadata with better structure
                if result is not None:
                    if isinstance(result, (str, int, float, bool)):
                        span.set_attribute("mcp.tool.result.value", str(result))
                        span.set_attribute("mcp.tool.result.type", type(result).__name__)
                    elif isinstance(result, list):
                        span.set_attribute("mcp.tool.result.count", len(result))
                        span.set_attribute("mcp.tool.result.type", "array")
                    elif isinstance(result, dict):
                        span.set_attribute("mcp.tool.result.count", len(result))
                        span.set_attribute("mcp.tool.result.type", "object")
                        if len(result) < 10:
                            span.set_attribute("mcp.tool.result.keys", ",".join(result.keys()))
                    elif hasattr(result, '__len__'):
                        span.set_attribute("mcp.tool.result.length", len(result))
                    
                    # For any result, record its type
                    span.set_attribute("mcp.tool.result.class", type(result).__name__)
                
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                
                # Add event for error
                span.add_event("tool.execution.error", {
                    "tool.name": tool_name,
                    "error.type": type(e).__name__,
                    "error.message": str(e),
                    "timestamp": trace.time_ns()
                })
                raise
        finally:
            # End the span and detach context
            span.end()
            context.detach(token)
            
            # Force flush the provider to ensure spans are exported
            global _provider
            if _provider:
                try:
                    _provider.force_flush(timeout_millis=1000)
                except Exception as e:
                    pass
    
    # Return appropriate wrapper based on function type
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

def instrument_resource(func: Callable[..., T], resource_uri: str) -> Callable[..., T]:
    """Instrument a resource function with OpenTelemetry tracing."""
    global _provider
    
    # If telemetry is disabled, return the original function
    if _provider is None:
        return func
    
    tracer = get_tracer()
    
    # Determine if this is a template based on URI pattern
    is_template = '{' in resource_uri
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        # Create a more descriptive span name
        span_name = f"mcp.resource.{'template' if is_template else 'static'}.read"
        with tracer.start_as_current_span(span_name) as span:
            # Add comprehensive attributes
            span.set_attribute("mcp.component.type", "resource")
            span.set_attribute("mcp.component.name", resource_uri)
            span.set_attribute("mcp.resource.uri", resource_uri)
            span.set_attribute("mcp.resource.is_template", is_template)
            span.set_attribute("mcp.resource.function", func.__name__)
            span.set_attribute("mcp.resource.module", func.__module__ if hasattr(func, '__module__') else "unknown")
            span.set_attribute("mcp.execution.async", True)
            
            # Extract Context parameter if present
            ctx = kwargs.get('ctx')
            if ctx:
                if hasattr(ctx, 'request_id'):
                    span.set_attribute("mcp.request.id", ctx.request_id)
                if hasattr(ctx, 'session_id'):
                    span.set_attribute("mcp.session.id", ctx.session_id)
                if hasattr(ctx, 'client_id'):
                    span.set_attribute("mcp.client.id", ctx.client_id)
            
            # Add event for resource read start
            span.add_event("resource.read.started", {
                "resource.uri": resource_uri,
                "timestamp": trace.time_ns()
            })
            
            try:
                result = await func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                
                # Add event for successful read
                span.add_event("resource.read.completed", {
                    "resource.uri": resource_uri,
                    "timestamp": trace.time_ns()
                })
                
                # Add result metadata
                if hasattr(result, '__len__'):
                    span.set_attribute("mcp.resource.result.size", len(result))
                
                # Determine content type if possible
                if isinstance(result, str):
                    span.set_attribute("mcp.resource.result.type", "text")
                    span.set_attribute("mcp.resource.result.length", len(result))
                elif isinstance(result, bytes):
                    span.set_attribute("mcp.resource.result.type", "binary")
                    span.set_attribute("mcp.resource.result.size_bytes", len(result))
                elif isinstance(result, dict):
                    span.set_attribute("mcp.resource.result.type", "object")
                    span.set_attribute("mcp.resource.result.keys_count", len(result))
                elif isinstance(result, list):
                    span.set_attribute("mcp.resource.result.type", "array")
                    span.set_attribute("mcp.resource.result.items_count", len(result))
                
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                
                # Add event for error
                span.add_event("resource.read.error", {
                    "resource.uri": resource_uri,
                    "error.type": type(e).__name__,
                    "error.message": str(e),
                    "timestamp": trace.time_ns()
                })
                raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        # Create a more descriptive span name
        span_name = f"mcp.resource.{'template' if is_template else 'static'}.read"
        with tracer.start_as_current_span(span_name) as span:
            # Add comprehensive attributes
            span.set_attribute("mcp.component.type", "resource")
            span.set_attribute("mcp.component.name", resource_uri)
            span.set_attribute("mcp.resource.uri", resource_uri)
            span.set_attribute("mcp.resource.is_template", is_template)
            span.set_attribute("mcp.resource.function", func.__name__)
            span.set_attribute("mcp.resource.module", func.__module__ if hasattr(func, '__module__') else "unknown")
            span.set_attribute("mcp.execution.async", False)
            
            # Extract Context parameter if present
            ctx = kwargs.get('ctx')
            if ctx:
                if hasattr(ctx, 'request_id'):
                    span.set_attribute("mcp.request.id", ctx.request_id)
                if hasattr(ctx, 'session_id'):
                    span.set_attribute("mcp.session.id", ctx.session_id)
                if hasattr(ctx, 'client_id'):
                    span.set_attribute("mcp.client.id", ctx.client_id)
            
            # Add event for resource read start
            span.add_event("resource.read.started", {
                "resource.uri": resource_uri,
                "timestamp": trace.time_ns()
            })
            
            try:
                result = func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                
                # Add event for successful read
                span.add_event("resource.read.completed", {
                    "resource.uri": resource_uri,
                    "timestamp": trace.time_ns()
                })
                
                # Add result metadata
                if hasattr(result, '__len__'):
                    span.set_attribute("mcp.resource.result.size", len(result))
                
                # Determine content type if possible
                if isinstance(result, str):
                    span.set_attribute("mcp.resource.result.type", "text")
                    span.set_attribute("mcp.resource.result.length", len(result))
                elif isinstance(result, bytes):
                    span.set_attribute("mcp.resource.result.type", "binary")
                    span.set_attribute("mcp.resource.result.size_bytes", len(result))
                elif isinstance(result, dict):
                    span.set_attribute("mcp.resource.result.type", "object")
                    span.set_attribute("mcp.resource.result.keys_count", len(result))
                elif isinstance(result, list):
                    span.set_attribute("mcp.resource.result.type", "array")
                    span.set_attribute("mcp.resource.result.items_count", len(result))
                    
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                
                # Add event for error
                span.add_event("resource.read.error", {
                    "resource.uri": resource_uri,
                    "error.type": type(e).__name__,
                    "error.message": str(e),
                    "timestamp": trace.time_ns()
                })
                raise
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

def instrument_prompt(func: Callable[..., T], prompt_name: str) -> Callable[..., T]:
    """Instrument a prompt function with OpenTelemetry tracing."""
    global _provider
    
    # If telemetry is disabled, return the original function
    if _provider is None:
        return func
    
    tracer = get_tracer()
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        # Create a more descriptive span name
        span_name = f"mcp.prompt.{prompt_name}.generate"
        with tracer.start_as_current_span(span_name) as span:
            # Add comprehensive attributes
            span.set_attribute("mcp.component.type", "prompt")
            span.set_attribute("mcp.component.name", prompt_name)
            span.set_attribute("mcp.prompt.name", prompt_name)
            span.set_attribute("mcp.prompt.function", func.__name__)
            span.set_attribute("mcp.prompt.module", func.__module__ if hasattr(func, '__module__') else "unknown")
            span.set_attribute("mcp.execution.async", True)
            
            # Extract Context parameter if present
            ctx = kwargs.get('ctx')
            if ctx:
                if hasattr(ctx, 'request_id'):
                    span.set_attribute("mcp.request.id", ctx.request_id)
                if hasattr(ctx, 'session_id'):
                    span.set_attribute("mcp.session.id", ctx.session_id)
                if hasattr(ctx, 'client_id'):
                    span.set_attribute("mcp.client.id", ctx.client_id)
            
            # Add prompt arguments
            for key, value in kwargs.items():
                if key != 'ctx':
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        span.set_attribute(f"mcp.prompt.arg.{key}", str(value))
                    else:
                        span.set_attribute(f"mcp.prompt.arg.{key}.type", type(value).__name__)
            
            # Add event for prompt generation start
            span.add_event("prompt.generation.started", {
                "prompt.name": prompt_name,
                "timestamp": trace.time_ns()
            })
            
            try:
                result = await func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                
                # Add event for successful generation
                span.add_event("prompt.generation.completed", {
                    "prompt.name": prompt_name,
                    "timestamp": trace.time_ns()
                })
                
                # Add message count and type information
                if isinstance(result, list):
                    span.set_attribute("mcp.prompt.result.message_count", len(result))
                    span.set_attribute("mcp.prompt.result.type", "message_list")
                    
                    # Analyze message types if they have role attributes
                    roles = []
                    for msg in result:
                        if hasattr(msg, 'role'):
                            roles.append(msg.role)
                        elif isinstance(msg, dict) and 'role' in msg:
                            roles.append(msg['role'])
                    
                    if roles:
                        unique_roles = list(set(roles))
                        span.set_attribute("mcp.prompt.result.roles", ",".join(unique_roles))
                        span.set_attribute("mcp.prompt.result.role_counts", str({role: roles.count(role) for role in unique_roles}))
                elif isinstance(result, str):
                    span.set_attribute("mcp.prompt.result.type", "string")
                    span.set_attribute("mcp.prompt.result.length", len(result))
                else:
                    span.set_attribute("mcp.prompt.result.type", type(result).__name__)
                    
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                
                # Add event for error
                span.add_event("prompt.generation.error", {
                    "prompt.name": prompt_name,
                    "error.type": type(e).__name__,
                    "error.message": str(e),
                    "timestamp": trace.time_ns()
                })
                raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        # Create a more descriptive span name
        span_name = f"mcp.prompt.{prompt_name}.generate"
        with tracer.start_as_current_span(span_name) as span:
            # Add comprehensive attributes
            span.set_attribute("mcp.component.type", "prompt")
            span.set_attribute("mcp.component.name", prompt_name)
            span.set_attribute("mcp.prompt.name", prompt_name)
            span.set_attribute("mcp.prompt.function", func.__name__)
            span.set_attribute("mcp.prompt.module", func.__module__ if hasattr(func, '__module__') else "unknown")
            span.set_attribute("mcp.execution.async", False)
            
            # Extract Context parameter if present
            ctx = kwargs.get('ctx')
            if ctx:
                if hasattr(ctx, 'request_id'):
                    span.set_attribute("mcp.request.id", ctx.request_id)
                if hasattr(ctx, 'session_id'):
                    span.set_attribute("mcp.session.id", ctx.session_id)
                if hasattr(ctx, 'client_id'):
                    span.set_attribute("mcp.client.id", ctx.client_id)
            
            # Add prompt arguments
            for key, value in kwargs.items():
                if key != 'ctx':
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        span.set_attribute(f"mcp.prompt.arg.{key}", str(value))
                    else:
                        span.set_attribute(f"mcp.prompt.arg.{key}.type", type(value).__name__)
            
            # Add event for prompt generation start
            span.add_event("prompt.generation.started", {
                "prompt.name": prompt_name,
                "timestamp": trace.time_ns()
            })
            
            try:
                result = func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                
                # Add event for successful generation
                span.add_event("prompt.generation.completed", {
                    "prompt.name": prompt_name,
                    "timestamp": trace.time_ns()
                })
                
                # Add message count and type information
                if isinstance(result, list):
                    span.set_attribute("mcp.prompt.result.message_count", len(result))
                    span.set_attribute("mcp.prompt.result.type", "message_list")
                    
                    # Analyze message types if they have role attributes
                    roles = []
                    for msg in result:
                        if hasattr(msg, 'role'):
                            roles.append(msg.role)
                        elif isinstance(msg, dict) and 'role' in msg:
                            roles.append(msg['role'])
                    
                    if roles:
                        unique_roles = list(set(roles))
                        span.set_attribute("mcp.prompt.result.roles", ",".join(unique_roles))
                        span.set_attribute("mcp.prompt.result.role_counts", str({role: roles.count(role) for role in unique_roles}))
                elif isinstance(result, str):
                    span.set_attribute("mcp.prompt.result.type", "string")
                    span.set_attribute("mcp.prompt.result.length", len(result))
                else:
                    span.set_attribute("mcp.prompt.result.type", type(result).__name__)
                    
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                
                # Add event for error
                span.add_event("prompt.generation.error", {
                    "prompt.name": prompt_name,
                    "error.type": type(e).__name__,
                    "error.message": str(e),
                    "timestamp": trace.time_ns()
                })
                raise
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

@asynccontextmanager
async def telemetry_lifespan(mcp_instance):
    """Simplified lifespan for telemetry initialization and cleanup."""
    global _provider, _instrumented_tools
    
    # Initialize telemetry with the server name
    provider = init_telemetry(service_name=mcp_instance.name)
    
    # If provider is None, telemetry is disabled
    if provider is None:
        # Just yield without any telemetry setup
        yield
        return
    
    # Try to add session tracking middleware if possible
    try:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request
        
        class SessionTracingMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                # Extract session ID from query params
                session_id = request.query_params.get('session_id')
                if session_id:
                    # Add to baggage for propagation
                    ctx = baggage.set_baggage("mcp.session.id", session_id)
                    from opentelemetry import context
                    token = context.attach(ctx)
                    
                    # Also create a span for the HTTP request
                    tracer = get_tracer()
                    with tracer.start_as_current_span(f"http.{request.method} {request.url.path}") as span:
                        span.set_attribute("http.method", request.method)
                        span.set_attribute("http.url", str(request.url))
                        span.set_attribute("http.session_id", session_id)
                        span.set_attribute("mcp.session.id", session_id)
                        
                        try:
                            response = await call_next(request)
                            span.set_attribute("http.status_code", response.status_code)
                            return response
                        finally:
                            context.detach(token)
                else:
                    return await call_next(request)
        
        # Try to add middleware to FastMCP app if it has Starlette app
        if hasattr(mcp_instance, 'app') or hasattr(mcp_instance, '_app'):
            app = getattr(mcp_instance, 'app', getattr(mcp_instance, '_app', None))
            if app and hasattr(app, 'add_middleware'):
                app.add_middleware(SessionTracingMiddleware)
    except Exception:
        pass
    
    try:
        # Yield control back to FastMCP
        yield
    finally:
        # Cleanup - shutdown the provider
        if _provider and hasattr(_provider, 'shutdown'):
            _provider.force_flush()
            _provider.shutdown()
            _provider = None 