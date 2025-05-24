"""Component-level OpenTelemetry instrumentation for Golf-built servers."""

import os
import sys
import functools
from typing import Any, Callable, Optional, TypeVar
from contextlib import asynccontextmanager
import asyncio

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Status, StatusCode, Span

T = TypeVar('T')

# Global tracer instance
_tracer: Optional[trace.Tracer] = None
_provider: Optional[TracerProvider] = None

def init_telemetry(service_name: str = "golf-mcp-server") -> TracerProvider:
    """Initialize OpenTelemetry with environment-based configuration."""
    global _provider
    
    # Check if already initialized
    current_provider = trace.get_tracer_provider()
    if not isinstance(current_provider, trace.NoOpTracerProvider):
        _provider = current_provider
        return current_provider
    
    # Configure based on environment
    exporter_type = os.environ.get("OTEL_TRACES_EXPORTER", "console").lower()
    
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
        print(f"[OTel] Configured OTLP exporter to {endpoint}", file=sys.stderr)
    else:
        # Default to console exporter
        exporter = ConsoleSpanExporter(out=sys.stderr)
        print(f"[OTel] Using console exporter", file=sys.stderr)
    
    # Add batch processor for better performance
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    
    # Set as global provider
    trace.set_tracer_provider(provider)
    _provider = provider
    
    print(f"[OTel] Telemetry initialized for service: {service_name}", file=sys.stderr)
    return provider

def get_tracer() -> trace.Tracer:
    """Get or create the global tracer instance."""
    global _tracer
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
    tracer = get_tracer()
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        with tracer.start_as_current_span(f"tool.{tool_name}") as span:
            _add_component_attributes(span, "tool", tool_name, 
                                     args_count=len(args),
                                     kwargs_count=len(kwargs))
            
            # Extract Context parameter if present
            ctx = kwargs.get('ctx')
            if ctx and hasattr(ctx, 'request_id'):
                span.set_attribute("mcp.request.id", ctx.request_id)
            
            try:
                result = await func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        with tracer.start_as_current_span(f"tool.{tool_name}") as span:
            _add_component_attributes(span, "tool", tool_name,
                                     args_count=len(args),
                                     kwargs_count=len(kwargs))
            
            # Extract Context parameter if present
            ctx = kwargs.get('ctx')
            if ctx and hasattr(ctx, 'request_id'):
                span.set_attribute("mcp.request.id", ctx.request_id)
            
            try:
                result = func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    
    # Return appropriate wrapper based on function type
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

def instrument_resource(func: Callable[..., T], resource_uri: str) -> Callable[..., T]:
    """Instrument a resource function with OpenTelemetry tracing."""
    tracer = get_tracer()
    
    # Determine if this is a template based on URI pattern
    is_template = '{' in resource_uri
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        span_name = "resource.template.read" if is_template else "resource.read"
        with tracer.start_as_current_span(span_name) as span:
            _add_component_attributes(span, "resource", resource_uri,
                                     is_template=is_template)
            
            # Extract Context parameter if present
            ctx = kwargs.get('ctx')
            if ctx and hasattr(ctx, 'request_id'):
                span.set_attribute("mcp.request.id", ctx.request_id)
            
            try:
                result = await func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                
                # Add result size if applicable
                if hasattr(result, '__len__'):
                    span.set_attribute("mcp.resource.size", len(result))
                
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        span_name = "resource.template.read" if is_template else "resource.read"
        with tracer.start_as_current_span(span_name) as span:
            _add_component_attributes(span, "resource", resource_uri,
                                     is_template=is_template)
            
            # Extract Context parameter if present
            ctx = kwargs.get('ctx')
            if ctx and hasattr(ctx, 'request_id'):
                span.set_attribute("mcp.request.id", ctx.request_id)
            
            try:
                result = func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                
                # Add result size if applicable
                if hasattr(result, '__len__'):
                    span.set_attribute("mcp.resource.size", len(result))
                    
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

def instrument_prompt(func: Callable[..., T], prompt_name: str) -> Callable[..., T]:
    """Instrument a prompt function with OpenTelemetry tracing."""
    tracer = get_tracer()
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        with tracer.start_as_current_span(f"prompt.{prompt_name}") as span:
            _add_component_attributes(span, "prompt", prompt_name)
            
            # Extract Context parameter if present
            ctx = kwargs.get('ctx')
            if ctx and hasattr(ctx, 'request_id'):
                span.set_attribute("mcp.request.id", ctx.request_id)
            
            try:
                result = await func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                
                # Add message count if result is a list
                if isinstance(result, list):
                    span.set_attribute("mcp.prompt.message_count", len(result))
                    
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        with tracer.start_as_current_span(f"prompt.{prompt_name}") as span:
            _add_component_attributes(span, "prompt", prompt_name)
            
            # Extract Context parameter if present
            ctx = kwargs.get('ctx')
            if ctx and hasattr(ctx, 'request_id'):
                span.set_attribute("mcp.request.id", ctx.request_id)
            
            try:
                result = func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                
                # Add message count if result is a list
                if isinstance(result, list):
                    span.set_attribute("mcp.prompt.message_count", len(result))
                    
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

@asynccontextmanager
async def telemetry_lifespan(mcp_instance):
    """Simplified lifespan for telemetry initialization and cleanup."""
    global _provider
    
    # Initialize telemetry with the server name
    provider = init_telemetry(service_name=mcp_instance.name)
    
    try:
        # Yield control back to FastMCP
        yield
    finally:
        # Cleanup - shutdown the provider
        if _provider and hasattr(_provider, 'shutdown'):
            print("[OTel] Shutting down telemetry provider", file=sys.stderr)
            _provider.force_flush()
            _provider.shutdown()
            _provider = None 