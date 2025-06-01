"""Builder for generating FastMCP manifests from parsed components."""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import black
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from golf.auth import get_auth_config
from golf.auth.api_key import get_api_key_config
from golf.core.builder_auth import generate_auth_code, generate_auth_routes
from golf.core.builder_telemetry import (
    generate_telemetry_imports,
    get_otel_dependencies,
)
from golf.core.config import Settings
from golf.core.parser import (
    ComponentType,
    ParsedComponent,
    parse_project,
)
from golf.core.transformer import transform_component

console = Console()


class ManifestBuilder:
    """Builds FastMCP manifest from parsed components."""

    def __init__(self, project_path: Path, settings: Settings) -> None:
        """Initialize the manifest builder.

        Args:
            project_path: Path to the project root
            settings: Project settings
        """
        self.project_path = project_path
        self.settings = settings
        self.components: dict[ComponentType, list[ParsedComponent]] = {}
        self.manifest: dict[str, Any] = {
            "name": settings.name,
            "description": settings.description or "",
            "tools": [],
            "resources": [],
            "prompts": [],
        }

    def build(self) -> dict[str, Any]:
        """Build the complete manifest.

        Returns:
            FastMCP manifest dictionary
        """
        # Parse all components
        self.components = parse_project(self.project_path)

        # Process each component type
        self._process_tools()
        self._process_resources()
        self._process_prompts()

        return self.manifest

    def _process_tools(self) -> None:
        """Process all tool components and add them to the manifest."""
        for component in self.components[ComponentType.TOOL]:
            # Extract the properties directly from the Input schema if it exists
            input_properties = {}
            required_fields = []

            if component.input_schema and "properties" in component.input_schema:
                input_properties = component.input_schema["properties"]
                # Get required fields if they exist
                if "required" in component.input_schema:
                    required_fields = component.input_schema["required"]

            # Create a flattened tool schema matching FastMCP documentation examples
            tool_schema = {
                "name": component.name,
                "description": component.docstring or "",
                "inputSchema": {
                    "type": "object",
                    "properties": input_properties,
                    "additionalProperties": False,
                    "$schema": "http://json-schema.org/draft-07/schema#",
                },
                "annotations": {"title": component.name.replace("-", " ").title()},
                "entry_function": component.entry_function,
            }

            # Include required fields if they exist
            if required_fields:
                tool_schema["inputSchema"]["required"] = required_fields

            # Add tool annotations if present
            if component.annotations:
                # Merge with existing annotations (keeping title)
                tool_schema["annotations"].update(component.annotations)

            # Add the tool to the manifest
            self.manifest["tools"].append(tool_schema)

    def _process_resources(self) -> None:
        """Process all resource components and add them to the manifest."""
        for component in self.components[ComponentType.RESOURCE]:
            if not component.uri_template:
                console.print(
                    f"[yellow]Warning: Resource {component.name} has no URI template[/yellow]"
                )
                continue

            resource_schema = {
                "uri": component.uri_template,
                "name": component.name,
                "description": component.docstring or "",
                "entry_function": component.entry_function,
            }

            # Add the resource to the manifest
            self.manifest["resources"].append(resource_schema)

    def _process_prompts(self) -> None:
        """Process all prompt components and add them to the manifest."""
        for component in self.components[ComponentType.PROMPT]:
            # For prompts, the handler will have to load the module and execute the run function
            # to get the actual messages, so we just register it by name
            prompt_schema = {
                "name": component.name,
                "description": component.docstring or "",
                "entry_function": component.entry_function,
            }

            # If the prompt has parameters, include them
            if component.parameters:
                arguments = []
                for param in component.parameters:
                    arguments.append(
                        {"name": param, "required": True}  # Default to required
                    )
                prompt_schema["arguments"] = arguments

            # Add the prompt to the manifest
            self.manifest["prompts"].append(prompt_schema)

    def save_manifest(self, output_path: Path | None = None) -> Path:
        """Save the manifest to a JSON file.

        Args:
            output_path: Path to save the manifest to (defaults to .golf/manifest.json)

        Returns:
            Path where the manifest was saved
        """
        if not output_path:
            # Create .golf directory if it doesn't exist
            golf_dir = self.project_path / ".golf"
            golf_dir.mkdir(exist_ok=True)
            output_path = golf_dir / "manifest.json"

        # Ensure parent directories exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the manifest to the file
        with open(output_path, "w") as f:
            json.dump(self.manifest, f, indent=2)

        console.print(f"[green]Manifest saved to {output_path}[/green]")
        return output_path


def build_manifest(project_path: Path, settings: Settings) -> dict[str, Any]:
    """Build a FastMCP manifest from parsed components.

    Args:
        project_path: Path to the project root
        settings: Project settings

    Returns:
        FastMCP manifest dictionary
    """
    # Use the ManifestBuilder class to build the manifest
    builder = ManifestBuilder(project_path, settings)
    return builder.build()


def compute_manifest_diff(
    old_manifest: dict[str, Any], new_manifest: dict[str, Any]
) -> dict[str, Any]:
    """Compute the difference between two manifests.

    Args:
        old_manifest: Previous manifest
        new_manifest: New manifest

    Returns:
        Dictionary describing the changes
    """
    diff = {
        "tools": {"added": [], "removed": [], "changed": []},
        "resources": {"added": [], "removed": [], "changed": []},
        "prompts": {"added": [], "removed": [], "changed": []},
    }

    # Helper function to extract names from a list of components
    def extract_names(components: list[dict[str, Any]]) -> set[str]:
        return {comp["name"] for comp in components}

    # Compare tools
    old_tools = extract_names(old_manifest.get("tools", []))
    new_tools = extract_names(new_manifest.get("tools", []))
    diff["tools"]["added"] = list(new_tools - old_tools)
    diff["tools"]["removed"] = list(old_tools - new_tools)

    # Compare tools that exist in both for changes
    for new_tool in new_manifest.get("tools", []):
        if new_tool["name"] in old_tools:
            # Find the corresponding old tool
            old_tool = next(
                (
                    t
                    for t in old_manifest.get("tools", [])
                    if t["name"] == new_tool["name"]
                ),
                None,
            )
            if old_tool and json.dumps(old_tool) != json.dumps(new_tool):
                diff["tools"]["changed"].append(new_tool["name"])

    # Compare resources
    old_resources = extract_names(old_manifest.get("resources", []))
    new_resources = extract_names(new_manifest.get("resources", []))
    diff["resources"]["added"] = list(new_resources - old_resources)
    diff["resources"]["removed"] = list(old_resources - new_resources)

    # Compare resources that exist in both for changes
    for new_resource in new_manifest.get("resources", []):
        if new_resource["name"] in old_resources:
            # Find the corresponding old resource
            old_resource = next(
                (
                    r
                    for r in old_manifest.get("resources", [])
                    if r["name"] == new_resource["name"]
                ),
                None,
            )
            if old_resource and json.dumps(old_resource) != json.dumps(new_resource):
                diff["resources"]["changed"].append(new_resource["name"])

    # Compare prompts
    old_prompts = extract_names(old_manifest.get("prompts", []))
    new_prompts = extract_names(new_manifest.get("prompts", []))
    diff["prompts"]["added"] = list(new_prompts - old_prompts)
    diff["prompts"]["removed"] = list(old_prompts - new_prompts)

    # Compare prompts that exist in both for changes
    for new_prompt in new_manifest.get("prompts", []):
        if new_prompt["name"] in old_prompts:
            # Find the corresponding old prompt
            old_prompt = next(
                (
                    p
                    for p in old_manifest.get("prompts", [])
                    if p["name"] == new_prompt["name"]
                ),
                None,
            )
            if old_prompt and json.dumps(old_prompt) != json.dumps(new_prompt):
                diff["prompts"]["changed"].append(new_prompt["name"])

    return diff


def has_changes(diff: dict[str, Any]) -> bool:
    """Check if a manifest diff contains any changes.

    Args:
        diff: Manifest diff from compute_manifest_diff

    Returns:
        True if there are any changes, False otherwise
    """
    for category in diff:
        for change_type in diff[category]:
            if diff[category][change_type]:
                return True

    return False


class CodeGenerator:
    """Code generator for FastMCP applications."""

    def __init__(
        self,
        project_path: Path,
        settings: Settings,
        output_dir: Path,
        build_env: str = "prod",
        copy_env: bool = False,
    ) -> None:
        """Initialize the code generator.

        Args:
            project_path: Path to the project root
            settings: Project settings
            output_dir: Directory to output the generated code
            build_env: Build environment ('dev' or 'prod')
            copy_env: Whether to copy environment variables to the built app
        """
        self.project_path = project_path
        self.settings = settings
        self.output_dir = output_dir
        self.build_env = build_env
        self.copy_env = copy_env
        self.components = {}
        self.manifest = {}
        self.common_files = {}
        self.import_map = {}

    def generate(self) -> None:
        """Generate the FastMCP application code."""
        # Parse the project and build the manifest
        with console.status("Analyzing project components..."):
            self.components = parse_project(self.project_path)
            self.manifest = build_manifest(self.project_path, self.settings)

            # Find common.py files and build import map
            self.common_files = find_common_files(self.project_path, self.components)
            self.import_map = build_import_map(self.project_path, self.common_files)

        # Create output directory structure
        with console.status("Creating directory structure..."):
            self._create_directory_structure()

        # Generate code for all components
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold green]Generating {task.description}"),
            console=console,
        ) as progress:
            tasks = [
                ("tools", self._generate_tools),
                ("resources", self._generate_resources),
                ("prompts", self._generate_prompts),
                ("server entry point", self._generate_server),
            ]

            for description, func in tasks:
                task = progress.add_task(description, total=1)
                func()
                progress.update(task, completed=1)

        # Get relative path for display
        try:
            output_dir_display = self.output_dir.relative_to(Path.cwd())
        except ValueError:
            output_dir_display = self.output_dir

        # Show success message with output directory
        console.print(
            f"[bold green]✓[/bold green] Build completed successfully in [bold]{output_dir_display}[/bold]"
        )

    def _create_directory_structure(self) -> None:
        """Create the output directory structure"""
        # Create main directories
        dirs = [
            self.output_dir,
            self.output_dir / "components",
            self.output_dir / "components" / "tools",
            self.output_dir / "components" / "resources",
            self.output_dir / "components" / "prompts",
        ]

        for directory in dirs:
            directory.mkdir(parents=True, exist_ok=True)
        # Process common.py files directly in the components directory
        self._process_common_files()

    def _process_common_files(self) -> None:
        """Process and transform common.py files in the components directory structure."""
        # Reuse the already fetched common_files instead of calling the function again
        for dir_path_str, common_file in self.common_files.items():
            # Convert string path to Path object
            dir_path = Path(dir_path_str)

            # Determine the component type
            component_type = None
            for part in dir_path.parts:
                if part in ["tools", "resources", "prompts"]:
                    component_type = part
                    break

            if not component_type:
                continue

            # Calculate target directory in components structure
            rel_to_component = dir_path.relative_to(component_type)
            target_dir = (
                self.output_dir / "components" / component_type / rel_to_component
            )

            # Create directory if it doesn't exist
            target_dir.mkdir(parents=True, exist_ok=True)

            # Create the common.py file in the target directory
            target_file = target_dir / "common.py"

            # Use transformer to process the file
            transform_component(
                component=None,
                output_file=target_file,
                project_path=self.project_path,
                import_map=self.import_map,
                source_file=common_file,
            )

    def _generate_tools(self) -> None:
        """Generate code for all tools."""
        tools_dir = self.output_dir / "components" / "tools"

        for tool in self.components.get(ComponentType.TOOL, []):
            # Get the tool directory structure
            rel_path = Path(tool.file_path).relative_to(self.project_path)
            if not rel_path.is_relative_to(Path(self.settings.tools_dir)):
                console.print(
                    f"[yellow]Warning: Tool {tool.name} is not in the tools directory[/yellow]"
                )
                continue

            try:
                rel_to_tools = rel_path.relative_to(self.settings.tools_dir)
                tool_dir = tools_dir / rel_to_tools.parent
            except ValueError:
                # Fall back to just using the filename
                tool_dir = tools_dir

            tool_dir.mkdir(parents=True, exist_ok=True)

            # Create the tool file
            output_file = tool_dir / rel_path.name
            transform_component(tool, output_file, self.project_path, self.import_map)

    def _generate_resources(self) -> None:
        """Generate code for all resources."""
        resources_dir = self.output_dir / "components" / "resources"

        for resource in self.components.get(ComponentType.RESOURCE, []):
            # Get the resource directory structure
            rel_path = Path(resource.file_path).relative_to(self.project_path)
            if not rel_path.is_relative_to(Path(self.settings.resources_dir)):
                console.print(
                    f"[yellow]Warning: Resource {resource.name} is not in the resources directory[/yellow]"
                )
                continue

            try:
                rel_to_resources = rel_path.relative_to(self.settings.resources_dir)
                resource_dir = resources_dir / rel_to_resources.parent
            except ValueError:
                # Fall back to just using the filename
                resource_dir = resources_dir

            resource_dir.mkdir(parents=True, exist_ok=True)

            # Create the resource file
            output_file = resource_dir / rel_path.name
            transform_component(
                resource, output_file, self.project_path, self.import_map
            )

    def _generate_prompts(self) -> None:
        """Generate code for all prompts."""
        prompts_dir = self.output_dir / "components" / "prompts"

        for prompt in self.components.get(ComponentType.PROMPT, []):
            # Get the prompt directory structure
            rel_path = Path(prompt.file_path).relative_to(self.project_path)
            if not rel_path.is_relative_to(Path(self.settings.prompts_dir)):
                console.print(
                    f"[yellow]Warning: Prompt {prompt.name} is not in the prompts directory[/yellow]"
                )
                continue

            try:
                rel_to_prompts = rel_path.relative_to(self.settings.prompts_dir)
                prompt_dir = prompts_dir / rel_to_prompts.parent
            except ValueError:
                # Fall back to just using the filename
                prompt_dir = prompts_dir

            prompt_dir.mkdir(parents=True, exist_ok=True)

            # Create the prompt file
            output_file = prompt_dir / rel_path.name
            transform_component(prompt, output_file, self.project_path, self.import_map)

    def _get_transport_config(self, transport_type: str) -> dict:
        """Get transport-specific configuration (primarily for endpoint path display).

        Args:
            transport_type: The transport type (e.g., 'sse', 'streamable-http', 'stdio')

        Returns:
            Dictionary with transport configuration details (endpoint_path)
        """
        config = {
            "endpoint_path": "",
        }

        if transport_type == "sse":
            config["endpoint_path"] = "/sse"  # Default SSE path for FastMCP
        elif transport_type == "stdio":
            config["endpoint_path"] = ""  # No HTTP endpoint
        else:
            # Default to streamable-http
            config["endpoint_path"] = "/mcp"  # Default MCP path for FastMCP

        return config

    def _generate_server(self) -> None:
        """Generate the main server entry point."""
        server_file = self.output_dir / "server.py"

        # Get auth components
        provider_config, _ = get_auth_config()
        auth_components = generate_auth_code(
            server_name=self.settings.name,
            host=self.settings.host,
            port=self.settings.port,
            https=False,  # This could be configurable in settings
            opentelemetry_enabled=self.settings.opentelemetry_enabled,
            transport=self.settings.transport,
        )

        # Create imports section
        imports = [
            "from fastmcp import FastMCP",
            "import os",
            "import sys",
            "from dotenv import load_dotenv",
            "import logging",
            "",
            "# Suppress FastMCP INFO logs",
            "logging.getLogger('fastmcp').setLevel(logging.WARNING)",
            "logging.getLogger('mcp').setLevel(logging.WARNING)",
            "",
        ]

        # Add auth imports if auth is configured
        if auth_components.get("has_auth"):
            imports.extend(auth_components["imports"])
            imports.append("")

        # Add OpenTelemetry imports if enabled
        if self.settings.opentelemetry_enabled:
            imports.extend(generate_telemetry_imports())
            imports.append("")

        # Add imports section for different transport methods
        if self.settings.transport == "sse" or self.settings.transport in [
            "streamable-http",
            "http",
        ]:
            imports.append("import uvicorn")

        # Add health check imports if enabled
        if self.settings.health_check_enabled:
            imports.extend(
                [
                    "from starlette.requests import Request",
                    "from starlette.responses import PlainTextResponse",
                ]
            )

        # Get transport-specific configuration
        transport_config = self._get_transport_config(self.settings.transport)
        endpoint_path = transport_config["endpoint_path"]

        # Track component modules to register
        component_registrations = []

        # Import components
        for component_type in self.components:
            # Add a section header
            if component_type == ComponentType.TOOL:
                imports.append("# Import tools")
                comp_section = "# Register tools"
            elif component_type == ComponentType.RESOURCE:
                imports.append("# Import resources")
                comp_section = "# Register resources"
            else:
                imports.append("# Import prompts")
                comp_section = "# Register prompts"

            component_registrations.append(comp_section)

            for component in self.components[component_type]:
                # Derive the import path based on component type and file path
                rel_path = Path(component.file_path).relative_to(self.project_path)
                module_name = rel_path.stem

                if component_type == ComponentType.TOOL:
                    try:
                        rel_to_tools = rel_path.relative_to(self.settings.tools_dir)
                        # Handle nested directories properly
                        if rel_to_tools.parent != Path("."):
                            parent_path = (
                                str(rel_to_tools.parent)
                                .replace("\\", ".")
                                .replace("/", ".")
                            )
                            import_path = f"components.tools.{parent_path}"
                        else:
                            import_path = "components.tools"
                    except ValueError:
                        import_path = "components.tools"
                elif component_type == ComponentType.RESOURCE:
                    try:
                        rel_to_resources = rel_path.relative_to(
                            self.settings.resources_dir
                        )
                        # Handle nested directories properly
                        if rel_to_resources.parent != Path("."):
                            parent_path = (
                                str(rel_to_resources.parent)
                                .replace("\\", ".")
                                .replace("/", ".")
                            )
                            import_path = f"components.resources.{parent_path}"
                        else:
                            import_path = "components.resources"
                    except ValueError:
                        import_path = "components.resources"
                else:  # PROMPT
                    try:
                        rel_to_prompts = rel_path.relative_to(self.settings.prompts_dir)
                        # Handle nested directories properly
                        if rel_to_prompts.parent != Path("."):
                            parent_path = (
                                str(rel_to_prompts.parent)
                                .replace("\\", ".")
                                .replace("/", ".")
                            )
                            import_path = f"components.prompts.{parent_path}"
                        else:
                            import_path = "components.prompts"
                    except ValueError:
                        import_path = "components.prompts"

                # Clean up the import path
                import_path = import_path.rstrip(".")

                # Add the import for the component's module
                full_module_path = f"{import_path}.{module_name}"
                imports.append(f"import {full_module_path}")

                # Add code to register this component
                if self.settings.opentelemetry_enabled:
                    # Use telemetry instrumentation
                    registration = f"# Register the {component_type.value} '{component.name}' with telemetry"
                    entry_func = (
                        component.entry_function
                        if hasattr(component, "entry_function")
                        and component.entry_function
                        else "export"
                    )

                    # Debug: Add logging to verify wrapping
                    registration += f"\n_wrapped_func = instrument_{component_type.value}({full_module_path}.{entry_func}, '{component.name}')"

                    if component_type == ComponentType.TOOL:
                        registration += f'\nmcp.add_tool(_wrapped_func, name="{component.name}", description="{component.docstring or ""}"'
                        # Add annotations if present
                        if hasattr(component, "annotations") and component.annotations:
                            registration += f", annotations={component.annotations}"
                        registration += ")"
                    elif component_type == ComponentType.RESOURCE:
                        registration += f'\nmcp.add_resource_fn(_wrapped_func, uri="{component.uri_template}", name="{component.name}", description="{component.docstring or ""}")'
                    else:  # PROMPT
                        registration += f'\nmcp.add_prompt(_wrapped_func, name="{component.name}", description="{component.docstring or ""}")'
                else:
                    # Standard registration without telemetry
                    if component_type == ComponentType.TOOL:
                        registration = f"# Register the tool '{component.name}' from {full_module_path}"

                        # Use the entry_function if available, otherwise try the export variable
                        if (
                            hasattr(component, "entry_function")
                            and component.entry_function
                        ):
                            registration += f"\nmcp.add_tool({full_module_path}.{component.entry_function}"
                        else:
                            registration += f"\nmcp.add_tool({full_module_path}.export"

                        # Add the name parameter
                        registration += f', name="{component.name}"'

                        # Add description from docstring
                        if component.docstring:
                            # Escape any quotes in the docstring
                            escaped_docstring = component.docstring.replace('"', '\\"')
                            registration += f', description="{escaped_docstring}"'

                        # Add annotations if present
                        if hasattr(component, "annotations") and component.annotations:
                            registration += f", annotations={component.annotations}"

                        registration += ")"

                    elif component_type == ComponentType.RESOURCE:
                        registration = f"# Register the resource '{component.name}' from {full_module_path}"

                        # Use the entry_function if available, otherwise try the export variable
                        if (
                            hasattr(component, "entry_function")
                            and component.entry_function
                        ):
                            registration += f'\nmcp.add_resource_fn({full_module_path}.{component.entry_function}, uri="{component.uri_template}"'
                        else:
                            registration += f'\nmcp.add_resource_fn({full_module_path}.export, uri="{component.uri_template}"'

                        # Add the name parameter
                        registration += f', name="{component.name}"'

                        # Add description from docstring
                        if component.docstring:
                            # Escape any quotes in the docstring
                            escaped_docstring = component.docstring.replace('"', '\\"')
                            registration += f', description="{escaped_docstring}"'

                        registration += ")"

                    else:  # PROMPT
                        registration = f"# Register the prompt '{component.name}' from {full_module_path}"

                        # Use the entry_function if available, otherwise try the export variable
                        if (
                            hasattr(component, "entry_function")
                            and component.entry_function
                        ):
                            registration += f"\nmcp.add_prompt({full_module_path}.{component.entry_function}"
                        else:
                            registration += (
                                f"\nmcp.add_prompt({full_module_path}.export"
                            )

                        # Add the name parameter
                        registration += f', name="{component.name}"'

                        # Add description from docstring
                        if component.docstring:
                            # Escape any quotes in the docstring
                            escaped_docstring = component.docstring.replace('"', '\\"')
                            registration += f', description="{escaped_docstring}"'

                        registration += ")"

                component_registrations.append(registration)

            # Add a blank line after each section
            imports.append("")
            component_registrations.append("")

        # Create environment section based on build type - moved after imports
        env_section = [
            "",
            "# Load environment variables from .env file if it exists",
            "# Note: dotenv will not override existing environment variables by default",
            "load_dotenv()",
            "",
        ]

        # OpenTelemetry setup code will be handled through imports and lifespan

        # Add auth setup code if auth is configured
        auth_setup_code = []
        if auth_components.get("has_auth"):
            auth_setup_code = auth_components["setup_code"]

        # Create FastMCP instance section
        server_code_lines = ["# Create FastMCP server"]

        # Build FastMCP constructor arguments
        mcp_constructor_args = [f'"{self.settings.name}"']

        # Add auth arguments if configured
        if auth_components.get("has_auth") and auth_components.get("fastmcp_args"):
            for key, value in auth_components["fastmcp_args"].items():
                mcp_constructor_args.append(f"{key}={value}")

        # Add OpenTelemetry parameters if enabled
        if self.settings.opentelemetry_enabled:
            mcp_constructor_args.append("lifespan=telemetry_lifespan")

        mcp_instance_line = f"mcp = FastMCP({', '.join(mcp_constructor_args)})"
        server_code_lines.append(mcp_instance_line)
        server_code_lines.append("")

        # Main entry point with transport-specific app initialization
        main_code = [
            'if __name__ == "__main__":',
            "    from rich.console import Console",
            "    from rich.panel import Panel",
            "    console = Console()",
            "    # Get configuration from environment variables or use defaults",
            '    host = os.environ.get("HOST", "127.0.0.1")',
            '    port = int(os.environ.get("PORT", 3000))',
            f'    transport_to_run = "{self.settings.transport}"',
            "",
        ]

        # Add startup message
        if self.settings.transport != "stdio":
            main_code.append(
                f'    console.print(Panel.fit(f"[bold green]{{mcp.name}}[/bold green]\\n[dim]Running on http://{{host}}:{{port}}{endpoint_path} with transport \\"{{transport_to_run}}\\" (environment: {self.build_env})[/dim]", border_style="green"))'
            )
        else:
            main_code.append(
                f'    console.print(Panel.fit(f"[bold green]{{mcp.name}}[/bold green]\\n[dim]Running with transport \\"{{transport_to_run}}\\" (environment: {self.build_env})[/dim]", border_style="green"))'
            )

        main_code.append("")

        # Transport-specific run methods
        if self.settings.transport == "sse":
            # Check if we need to add API key middleware for SSE
            api_key_config = get_api_key_config()
            if auth_components.get("has_auth") and api_key_config:
                main_code.extend(
                    [
                        "    # For SSE with API key auth, we need to get the app and add middleware",
                        '    app = mcp.http_app(transport="sse")',
                        "    app.add_middleware(ApiKeyMiddleware)",
                    ]
                )
            else:
                main_code.extend(
                    [
                        "    # For SSE, get the app to add middleware",
                        '    app = mcp.http_app(transport="sse")',
                    ]
                )

            # Add OpenTelemetry middleware to the SSE app if enabled
            if self.settings.opentelemetry_enabled:
                main_code.extend(
                    [
                        "    # Apply OpenTelemetry middleware to the SSE app",
                        "    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware",
                        "    app = OpenTelemetryMiddleware(app)",
                    ]
                )

            main_code.extend(
                [
                    "    # Run with the configured app",
                    '    uvicorn.run(app, host=host, port=port, log_level="info")',
                ]
            )
        elif self.settings.transport in ["streamable-http", "http"]:
            main_code.extend(
                [
                    "    # Create HTTP app and run with uvicorn",
                    "    app = mcp.http_app()",
                ]
            )

            # Check if we need to add API key middleware
            api_key_config = get_api_key_config()
            if auth_components.get("has_auth") and api_key_config:
                main_code.extend(
                    [
                        "    # Add API key middleware",
                        "    app.add_middleware(ApiKeyMiddleware)",
                    ]
                )

            # Add OpenTelemetry middleware to the HTTP app if enabled
            if self.settings.opentelemetry_enabled:
                main_code.extend(
                    [
                        "    # Apply OpenTelemetry middleware to the HTTP app",
                        "    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware",
                        "    app = OpenTelemetryMiddleware(app)",
                    ]
                )

            main_code.extend(
                ['    uvicorn.run(app, host=host, port=port, log_level="info")']
            )
        else:
            # For stdio transport, use mcp.run()
            main_code.extend(
                ["    # Run with stdio transport", '    mcp.run(transport="stdio")']
            )

        # Add health check route if enabled
        health_check_code = []
        if self.settings.health_check_enabled:
            health_check_code = [
                "# Add health check route",
                "@mcp.custom_route('"
                + self.settings.health_check_path
                + '\', methods=["GET"])',
                "async def health_check(request: Request) -> PlainTextResponse:",
                '    """Health check endpoint for Kubernetes and load balancers."""',
                f'    return PlainTextResponse("{self.settings.health_check_response}")',
                "",
            ]

        # Combine all sections
        # Order: imports, env_section, auth_setup, server_code (mcp init),
        # post_init (API key middleware), component_registrations, main_code (run block)
        code = "\n".join(
            imports
            + env_section
            + auth_setup_code
            + server_code_lines
            + component_registrations
            + health_check_code
            + main_code
        )

        # Format with black
        try:
            code = black.format_str(code, mode=black.Mode())
        except Exception as e:
            console.print(f"[yellow]Warning: Could not format server.py: {e}[/yellow]")

        # Write to file
        with open(server_file, "w") as f:
            f.write(code)


def build_project(
    project_path: Path,
    settings: Settings,
    output_dir: Path,
    build_env: str = "prod",
    copy_env: bool = False,
) -> None:
    """Build a standalone FastMCP application from a GolfMCP project.

    Args:
        project_path: Path to the project directory
        settings: Project settings
        output_dir: Output directory for the built application
        build_env: Build environment ('dev' or 'prod')
        copy_env: Whether to copy environment variables to the built app
    """
    # Execute pre_build.py if it exists
    pre_build_path = project_path / "pre_build.py"
    if pre_build_path.exists():
        try:
            # Save the current directory and path
            original_dir = os.getcwd()
            original_path = sys.path.copy()

            # Change to the project directory and add it to Python path
            os.chdir(project_path)
            sys.path.insert(0, str(project_path))

            # Execute the pre_build script
            with open(pre_build_path) as f:
                script_content = f.read()

            # Print the first few lines for debugging
            "\n".join(script_content.split("\n")[:5]) + "\n..."

            # Use exec to run the script as a module
            code = compile(script_content, str(pre_build_path), "exec")
            exec(code, {})

            # Check if auth was configured by the script
            provider, scopes = get_auth_config()

            # Restore original directory and path
            os.chdir(original_dir)
            sys.path = original_path

        except Exception as e:
            console.print(f"[red]Error executing pre_build.py: {str(e)}[/red]")
            import traceback

            console.print(f"[red]{traceback.format_exc()}[/red]")

            # Track detailed error for pre_build.py execution failures
            try:
                from golf.core.telemetry import track_detailed_error

                track_detailed_error(
                    "build_pre_build_failed",
                    e,
                    context="Executing pre_build.py configuration script",
                    operation="pre_build_execution",
                    additional_props={
                        "file_path": str(pre_build_path.relative_to(project_path)),
                        "build_env": build_env,
                    },
                )
            except Exception:
                # Don't let telemetry errors break the build
                pass

    # Clear the output directory if it exists
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(
        parents=True, exist_ok=True
    )  # Ensure output_dir exists after clearing

    # --- BEGIN Enhanced .env handling ---
    env_vars_to_write = {}
    env_file_path = output_dir / ".env"

    # 1. Load from existing project .env if copy_env is true
    if copy_env:
        project_env_file = project_path / ".env"
        if project_env_file.exists():
            try:
                from dotenv import dotenv_values

                env_vars_to_write.update(dotenv_values(project_env_file))
            except ImportError:
                console.print(
                    "[yellow]Warning: python-dotenv is not installed. Cannot read existing .env file for rich merging. Copying directly.[/yellow]"
                )
                try:
                    shutil.copy(project_env_file, env_file_path)
                    # If direct copy happens, re-read for step 2 & 3 to respect its content
                    if env_file_path.exists():
                        from dotenv import dotenv_values

                        env_vars_to_write.update(
                            dotenv_values(env_file_path)
                        )  # Read what was copied
                except Exception as e:
                    console.print(
                        f"[yellow]Warning: Could not copy project .env file: {e}[/yellow]"
                    )
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Error reading project .env file content: {e}[/yellow]"
                )

    # 2. Apply Golf's OTel default exporter setting if OTEL_TRACES_EXPORTER is not already set
    if settings.opentelemetry_enabled and settings.opentelemetry_default_exporter:
        if "OTEL_TRACES_EXPORTER" not in env_vars_to_write:
            env_vars_to_write["OTEL_TRACES_EXPORTER"] = (
                settings.opentelemetry_default_exporter
            )
            console.print(
                f"[info]Setting OTEL_TRACES_EXPORTER to '{settings.opentelemetry_default_exporter}' from golf.json in built app's .env[/info]"
            )

    # 3. Apply Golf's project name as OTEL_SERVICE_NAME if not already set
    # (Ensures service name defaults to project name if not specified in user's .env)
    if settings.opentelemetry_enabled and settings.name:
        if "OTEL_SERVICE_NAME" not in env_vars_to_write:
            env_vars_to_write["OTEL_SERVICE_NAME"] = settings.name

    # 4. (Re-)Write the .env file in the output directory if there's anything to write
    if env_vars_to_write:
        try:
            with open(env_file_path, "w") as f:
                for key, value in env_vars_to_write.items():
                    # Ensure values are properly quoted if they contain spaces or special characters
                    # and handle existing quotes within the value.
                    if isinstance(value, str):
                        # Replace backslashes first, then double quotes
                        processed_value = value.replace(
                            "\\", "\\\\"
                        )  # Escape backslashes
                        processed_value = processed_value.replace(
                            '"', '\\"'
                        )  # Escape double quotes
                        if (
                            " " in value
                            or "#" in value
                            or "\n" in value
                            or '"' in value
                            or "'" in value
                        ):
                            f.write(f'{key}="{processed_value}"\n')
                        else:
                            f.write(f"{key}={processed_value}\n")
                    else:  # For non-string values, write directly
                        f.write(f"{key}={value}\n")
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not write .env file to output directory: {e}[/yellow]"
            )
    # --- END Enhanced .env handling ---

    # Show what we're building, with environment info
    console.print(
        f"[bold]Building [green]{settings.name}[/green] ({build_env} environment)[/bold]"
    )

    # Generate the code
    generator = CodeGenerator(
        project_path, settings, output_dir, build_env=build_env, copy_env=copy_env
    )
    generator.generate()

    # Create a simple README
    readme_content = f"""# {settings.name}

Generated FastMCP application ({build_env} environment).

## Running the server

```bash
cd {output_dir.name}
python server.py
```

This is a standalone FastMCP server generated by GolfMCP.
"""

    with open(output_dir / "README.md", "w") as f:
        f.write(readme_content)

    # Copy pyproject.toml with required dependencies
    base_dependencies = [
        "fastmcp>=2.0.0",
        "uvicorn>=0.20.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
    ]

    # Add OpenTelemetry dependencies if enabled
    if settings.opentelemetry_enabled:
        base_dependencies.extend(get_otel_dependencies())

    # Add authentication dependencies if enabled, before generating pyproject_content
    provider_config, required_scopes = (
        get_auth_config()
    )  # Ensure this is called to check for auth
    if provider_config:
        base_dependencies.extend(
            [
                "pyjwt>=2.0.0",
                "httpx>=0.20.0",
            ]
        )

    # Create the dependencies string
    dependencies_str = ",\n    ".join([f'"{dep}"' for dep in base_dependencies])

    pyproject_content = f"""[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "generated-fastmcp-app"
version = "0.1.0"
description = "Generated FastMCP Application"
requires-python = ">=3.10"
dependencies = [
    {dependencies_str}
]
"""

    with open(output_dir / "pyproject.toml", "w") as f:
        f.write(pyproject_content)

    # Always copy the auth module so it's available
    auth_dir = output_dir / "golf" / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py with needed exports
    with open(auth_dir / "__init__.py", "w") as f:
        f.write(
            """\"\"\"Auth module for GolfMCP.\"\"\"

from golf.auth.provider import ProviderConfig
from golf.auth.oauth import GolfOAuthProvider, create_callback_handler
from golf.auth.helpers import get_access_token, get_provider_token, extract_token_from_header, get_api_key, set_api_key
from golf.auth.api_key import configure_api_key, get_api_key_config
"""
        )

    # Copy provider, oauth, and helper modules
    for module in ["provider.py", "oauth.py", "helpers.py", "api_key.py"]:
        src_file = Path(__file__).parent.parent.parent / "golf" / "auth" / module
        dst_file = auth_dir / module

        if src_file.exists():
            shutil.copy(src_file, dst_file)
        else:
            console.print(
                f"[yellow]Warning: Could not find {src_file} to copy[/yellow]"
            )

    # Copy telemetry module if OpenTelemetry is enabled
    if settings.opentelemetry_enabled:
        telemetry_dir = output_dir / "golf" / "telemetry"
        telemetry_dir.mkdir(parents=True, exist_ok=True)

        # Copy telemetry __init__.py
        src_init = (
            Path(__file__).parent.parent.parent / "golf" / "telemetry" / "__init__.py"
        )
        dst_init = telemetry_dir / "__init__.py"
        if src_init.exists():
            shutil.copy(src_init, dst_init)

        # Copy instrumentation module
        src_instrumentation = (
            Path(__file__).parent.parent.parent
            / "golf"
            / "telemetry"
            / "instrumentation.py"
        )
        dst_instrumentation = telemetry_dir / "instrumentation.py"
        if src_instrumentation.exists():
            shutil.copy(src_instrumentation, dst_instrumentation)
        else:
            console.print(
                "[yellow]Warning: Could not find telemetry instrumentation module[/yellow]"
            )

    # Check if auth routes need to be added
    provider_config, _ = get_auth_config()
    if provider_config:
        auth_routes_code = generate_auth_routes()

        server_file = output_dir / "server.py"
        if server_file.exists():
            with open(server_file) as f:
                server_code_content = f.read()

            # Add auth routes before the main block
            app_marker = 'if __name__ == "__main__":'
            app_pos = server_code_content.find(app_marker)
            if app_pos != -1:
                modified_code = (
                    server_code_content[:app_pos]
                    + auth_routes_code
                    + "\n\n"
                    + server_code_content[app_pos:]
                )

                # Format with black before writing
                try:
                    final_code_to_write = black.format_str(
                        modified_code, mode=black.Mode()
                    )
                except Exception as e:
                    console.print(
                        f"[yellow]Warning: Could not format server.py after auth routes injection: {e}[/yellow]"
                    )
                    final_code_to_write = modified_code

                with open(server_file, "w") as f:
                    f.write(final_code_to_write)
            else:
                console.print(
                    f"[yellow]Warning: Could not find main block marker '{app_marker}' in {server_file} to inject auth routes.[/yellow]"
                )


# Renamed function - was find_shared_modules
def find_common_files(
    project_path: Path, components: dict[ComponentType, list[ParsedComponent]]
) -> dict[str, Path]:
    """Find all common.py files used by components."""
    # We'll use the parser's functionality to find common files directly
    from golf.core.parser import parse_common_files

    common_files = parse_common_files(project_path)

    # Return the found files without debug messages
    return common_files


# Updated parameter name from shared_modules to common_files
def build_import_map(
    project_path: Path, common_files: dict[str, Path]
) -> dict[str, str]:
    """Build a mapping of import paths to their new locations in the build output.

    This maps from original relative import paths to absolute import paths
    in the components directory structure.
    """
    import_map = {}

    for dir_path_str, _file_path in common_files.items():
        # Convert string path to Path object
        dir_path = Path(dir_path_str)

        # Get the component type (tools, resources, prompts)
        component_type = None
        for part in dir_path.parts:
            if part in ["tools", "resources", "prompts"]:
                component_type = part
                break

        if not component_type:
            continue

        # Calculate the relative path within the component type
        try:
            rel_to_component = dir_path.relative_to(component_type)
            # Create the new import path
            if str(rel_to_component) == ".":
                # This is at the root of the component type
                new_path = f"components.{component_type}"
            else:
                # Replace path separators with dots
                path_parts = str(rel_to_component).replace("\\", "/").split("/")
                new_path = f"components.{component_type}.{'.'.join(path_parts)}"

            # Map both the directory and the common file
            orig_module = dir_path_str
            import_map[orig_module] = new_path

            # Also map the specific common module
            common_module = f"{dir_path_str}/common"
            import_map[common_module] = f"{new_path}.common"
        except ValueError:
            continue

    return import_map
