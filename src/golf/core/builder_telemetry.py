"""OpenTelemetry integration for the GolfMCP build process.

This module provides functions for generating OpenTelemetry initialization
and instrumentation code for FastMCP servers built with GolfMCP.
"""


def generate_telemetry_imports() -> list[str]:
    """Generate import statements for telemetry instrumentation.

    Returns:
        List of import statements for telemetry
    """
    return [
        "# OpenTelemetry instrumentation imports",
        "from golf.telemetry import (",
        "    instrument_tool,",
        "    instrument_resource,",
        "    instrument_prompt,",
        "    telemetry_lifespan,",
        ")",
    ]


def generate_component_registration_with_telemetry(
    component_type: str,
    component_name: str,
    module_path: str,
    entry_function: str,
    docstring: str = "",
    uri_template: str = None,
) -> str:
    """Generate component registration code with telemetry instrumentation.

    Args:
        component_type: Type of component ('tool', 'resource', 'prompt')
        component_name: Name of the component
        module_path: Full module path to the component
        entry_function: Entry function name
        docstring: Component description
        uri_template: URI template for resources (optional)

    Returns:
        Python code string for registering the component with instrumentation
    """
    func_ref = f"{module_path}.{entry_function}"
    escaped_docstring = docstring.replace('"', '\\"') if docstring else ""

    if component_type == "tool":
        wrapped_func = f"instrument_tool({func_ref}, '{component_name}')"
        return f'mcp.add_tool({wrapped_func}, name="{component_name}", description="{escaped_docstring}")'

    elif component_type == "resource":
        wrapped_func = f"instrument_resource({func_ref}, '{uri_template}')"
        return f'mcp.add_resource_fn({wrapped_func}, uri="{uri_template}", name="{component_name}", description="{escaped_docstring}")'

    elif component_type == "prompt":
        wrapped_func = f"instrument_prompt({func_ref}, '{component_name}')"
        return f'mcp.add_prompt({wrapped_func}, name="{component_name}", description="{escaped_docstring}")'

    else:
        raise ValueError(f"Unknown component type: {component_type}")


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
    ]
