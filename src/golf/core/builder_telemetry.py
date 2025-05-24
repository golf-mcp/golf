"""OpenTelemetry integration for the GolfMCP build process.

This module provides functions for generating OpenTelemetry initialization
and instrumentation code for FastMCP servers built with GolfMCP.
"""

from golf import __version__

def generate_otel_lifespan_code(default_exporter: str = "console", project_name: str = "golf-mcp-server") -> str:
    """Generate code for the OpenTelemetry lifespan function.
    
    Args:
        default_exporter: Default exporter type if not set in environment
        project_name: Default service name if not set in environment
        
    Returns:
        Python code string for the OpenTelemetry lifespan function
    """
    return f'''
# --- OpenTelemetry Early Initialization ---
# Initialize OpenTelemetry as early as possible to prevent other modules from auto-initializing
import os
import sys
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource as OtelResource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

# Initialize immediately if environment variables are set
if os.environ.get("OTEL_SERVICE_NAME") or os.environ.get("OTEL_TRACES_EXPORTER"):
    service_name = os.environ.get("OTEL_SERVICE_NAME", "{project_name}")
    exporter_type = os.environ.get("OTEL_TRACES_EXPORTER", "{default_exporter}").lower()
    
    print(f"[OTel] Early initialization with service={{service_name}}, exporter={{exporter_type}}", file=sys.stderr)
    
    resource = OtelResource.create({{"service.name": service_name}})
    provider = TracerProvider(resource=resource)
    
    if exporter_type == "otlp_http":
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        exporter = OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()
    else:
        exporter = ConsoleSpanExporter(out=sys.stderr)
    
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    
    # Store for later reference
    _golf_otel_provider_global = provider
    _golf_otel_initialized_flag = True
else:
    _golf_otel_provider_global = None
    _golf_otel_initialized_flag = False

# --- OpenTelemetry Lifespan Start ---
# These variables are global within the generated server.py module scope
# (Already initialized above if env vars were set)

from contextlib import asynccontextmanager
import logging
from opentelemetry.trace import NoOpTracerProvider

# Optional: Configure OpenTelemetry's own logger to be less verbose
# logging.getLogger('opentelemetry').setLevel(logging.WARNING)

@asynccontextmanager
async def otel_lifespan(app): # 'app' is the FastMCP instance passed by _lifespan_wrapper
    global _golf_otel_provider_global, _golf_otel_initialized_flag
    
    # These will be resolved when otel_lifespan runs in the generated server.py
    # .format() inserts build-time fallbacks {project_name} and {default_exporter}
    service_name_to_use = os.environ.get("OTEL_SERVICE_NAME", "{project_name}")
    exporter_type_to_use = os.environ.get("OTEL_TRACES_EXPORTER", "{default_exporter}").lower()
    
    # Local variable for the provider created in this specific call, if any.
    local_provider_instance_for_shutdown = None
    
    try:
        if not _golf_otel_initialized_flag:
            # Double check if a real provider is already globally set by another mechanism
            # trace.get_tracer_provider() returns a NoOpTracerProvider by default.
            current_global_otel_provider = trace.get_tracer_provider()
            if isinstance(current_global_otel_provider, NoOpTracerProvider):
                print(f"[OTel] Initializing OpenTelemetry Globals (service={{service_name_to_use}}, exporter={{exporter_type_to_use}})...", file=sys.stderr)
                
                resource = OtelResource.create({{"service.name": service_name_to_use}})
                provider_to_set = TracerProvider(resource=resource)
                
                exporter = None
                if exporter_type_to_use == "otlp_http":
                    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
                    exporter = OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()
                else: # Default to console
                    exporter = ConsoleSpanExporter(out=sys.stderr)  # Ensure console output goes to stderr
                
                processor = BatchSpanProcessor(exporter)
                provider_to_set.add_span_processor(processor)
                
                trace.set_tracer_provider(provider_to_set)
                _golf_otel_provider_global = provider_to_set  # Store it globally
                _golf_otel_initialized_flag = True
                local_provider_instance_for_shutdown = provider_to_set  # Mark for shutdown by this invocation
                print(f"[OTel] Global OpenTelemetry provider SET (service={{service_name_to_use}}, exporter={{exporter_type_to_use}})", file=sys.stderr)
            else:
                # A real provider is already set globally. Do not override.
                # Assign it to _golf_otel_provider_global if not already assigned, for consistency,
                # but don't mark it for shutdown by this specific lifespan invocation.
                if _golf_otel_provider_global is None:
                    _golf_otel_provider_global = current_global_otel_provider
                _golf_otel_initialized_flag = True  # Mark as initialized to prevent re-entry by this mechanism
                print(f"[OTel] Global OpenTelemetry provider was ALREADY SET (service={{service_name_to_use}}). Using existing.", file=sys.stderr)
        else:
            # print(f"[OTel Lifespan DEBUG] Already initialized by this mechanism. Yielding.", file=sys.stderr)
            pass  # Already initialized by this mechanism in a previous entry
        
        yield {{}}  # Application runs here
        
    except Exception as e:
        print("[OTel] ERROR during OpenTelemetry setup/yield: " + str(e), file=sys.stderr)
        import traceback
        print(traceback.format_exc(), file=sys.stderr)
        raise
    finally:
        # Only the instance of otel_lifespan that successfully initialized the provider
        # should be responsible for its shutdown.
        if local_provider_instance_for_shutdown:
            # print(f"[OTel Lifespan DEBUG] Shutting down OTel Provider for service={{service_name_to_use}}.", file=sys.stderr)
            local_provider_instance_for_shutdown.shutdown()
            _golf_otel_initialized_flag = False  # Allow re-init if server process truly restarts
            _golf_otel_provider_global = None
            print("[OTel] Provider shut down by this lifespan instance.", file=sys.stderr)

# --- OpenTelemetry Lifespan End ---
'''

def generate_otel_instrumentation_code() -> str:
    """Generate code for instrumenting the FastMCP instance.
    
    Returns:
        Python code string for instrumenting FastMCP methods
    """
    return f"""
# Instrument FastMCP instance
import wrapt
import json
import sys # For debug prints
from opentelemetry import trace as otel_trace
from opentelemetry.trace import SpanKind, Status, StatusCode

print("[OTel Instrumentation] Applying FastMCP method wrappers...", file=sys.stderr)

# Create a tracer for the instrumentation
otel_tracer = otel_trace.get_tracer("golfmcp.fastmcp", "{__version__}")
print(f"[OTel Instrumentation] Acquired tracer: {{str(otel_tracer)}}", file=sys.stderr)

def otel_operation_wrapper(operation_name_suffix):
    def wrapper(wrapped, instance, args, kwargs):
        component_name = args[0] if args else "unknown"
        span_name = "mcp." + operation_name_suffix
        # print(f"[OTel Instrumentation DEBUG] Wrapping: {{instance.name}}.{{operation_name_suffix}} for component: {{component_name}}", file=sys.stderr)
        
        with otel_tracer.start_as_current_span(span_name, kind=SpanKind.SERVER) as span:
            # print(f"[OTel Instrumentation DEBUG] Started span: {{span_name}}, Trace ID: {{span.get_span_context().trace_id}}", file=sys.stderr)
            span.set_attribute("rpc.system", "mcp")
            span.set_attribute("rpc.method", operation_name_suffix)
            span.set_attribute("rpc.service", instance.name)
            
            # Set operation-specific attributes
            if component_name != "unknown":
                component_type = operation_name_suffix.split("_")[1] if "_" in operation_name_suffix else "component"
                span.set_attribute("mcp." + component_type + ".name", str(component_name))
            
            # For call_tool, add parameters (carefully, to avoid sensitive data)
            if operation_name_suffix == "call_tool" and len(args) > 1 and args[1]:
                try:
                    params_str = json.dumps(args[1])
                    # Truncate long parameter strings to avoid huge spans
                    span.set_attribute("mcp.request.arguments", params_str[:1024] if len(params_str) > 1024 else params_str)
                except Exception:
                    span.set_attribute("mcp.request.arguments", "[serialization_error]")
            
            try:
                # Call the original method
                result = wrapped(*args, **kwargs)
                
                # Set success status
                span.set_status(Status(StatusCode.OK))
                
                # Add result count for list operations
                if "list" in operation_name_suffix and isinstance(result, list):
                    span.set_attribute("mcp.response.count", len(result))
                
                return result
            except Exception as e:
                # Record the exception and set error status
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    
    return wrapper

# Define the methods to instrument
methods_to_patch = [
    ("_mcp_call_tool", "call_tool"),
    ("_mcp_read_resource", "read_resource"),
    ("_mcp_get_prompt", "get_prompt"),
    ("_mcp_list_tools", "list_tools"),
    ("_mcp_list_resources", "list_resources"),
    ("_mcp_list_resource_templates", "list_resource_templates"),
    ("_mcp_list_prompts", "list_prompts")
]

# Apply instrumentation to each method
# This code runs in server.py *after* 'mcp' is defined.
# The 'mcp' variable needs to be in the scope where this instrumentation code is placed.
for method_name, operation_suffix in methods_to_patch:
    if hasattr(mcp, method_name): # 'mcp' should be the FastMCP instance
        # print(f"[OTel Instrumentation DEBUG] Patching {{method_name}} on {{mcp}}", file=sys.stderr)
        wrapt.wrap_function_wrapper(mcp, method_name, otel_operation_wrapper(operation_suffix))

print("[OTel Instrumentation] MCP method instrumentation attempted.", file=sys.stderr)
"""

def get_otel_dependencies() -> list[str]:
    """Get list of OpenTelemetry dependencies to add to pyproject.toml.
    
    Returns:
        List of package requirements strings
    """
    return [
        "opentelemetry-api>=1.18.0",
        "opentelemetry-sdk>=1.18.0",
        "opentelemetry-instrumentation-asgi>=0.40b0",
        "opentelemetry-exporter-otlp-proto-http>=0.40b0",
        "wrapt>=1.14.0",
    ]
