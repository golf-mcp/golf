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
    is_template: bool = False,
) -> str:
    """Generate component registration code with telemetry instrumentation.

    Args:
        component_type: Type of component ('tool', 'resource', 'prompt')
        component_name: Name of the component
        module_path: Full module path to the component
        entry_function: Entry function name
        docstring: Component description
        uri_template: URI template for resources (optional)
        is_template: Whether the resource is a template (has URI parameters)

    Returns:
        Python code string for registering the component with instrumentation
    """
    func_ref = f"{module_path}.{entry_function}"
    escaped_docstring = docstring.replace('"', '\\"') if docstring else ""

    if component_type == "tool":
        wrapped_func = f"instrument_tool({func_ref}, '{component_name}')"
        return (
            f"_tool = Tool.from_function({wrapped_func}, "
            f'name="{component_name}", description="{escaped_docstring}")\n'
            f"mcp.add_tool(_tool)"
        )

    elif component_type == "resource":
        wrapped_func = f"instrument_resource({func_ref}, '{uri_template}')"
        if is_template:
            return (
                f"_resource = ResourceTemplate.from_function({wrapped_func}, "
                f'uri_template="{uri_template}", name="{component_name}", '
                f'description="{escaped_docstring}")\n'
                f"mcp.add_template(_resource)"
            )
        else:
            return (
                f"_resource = Resource.from_function({wrapped_func}, "
                f'uri="{uri_template}", name="{component_name}", '
                f'description="{escaped_docstring}")\n'
                f"mcp.add_resource(_resource)"
            )

    elif component_type == "prompt":
        wrapped_func = f"instrument_prompt({func_ref}, '{component_name}')"
        return (
            f"_prompt = Prompt.from_function({wrapped_func}, "
            f'name="{component_name}", description="{escaped_docstring}")\n'
            f"mcp.add_prompt(_prompt)"
        )

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
