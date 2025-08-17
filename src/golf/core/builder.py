"""Builder for generating FastMCP manifests from parsed components."""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import black
from rich.console import Console

from golf.auth import is_auth_configured
from golf.auth.api_key import get_api_key_config
from golf.core.builder_auth import generate_auth_code, generate_auth_routes
from golf.core.builder_telemetry import (
    generate_telemetry_imports,
)
from golf.cli.branding import create_build_header, get_status_text, STATUS_ICONS, GOLF_BLUE
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
                console.print(f"[yellow]Warning: Resource {component.name} has no URI template[/yellow]")
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
            # For prompts, the handler will have to load the module and execute
            # the run function
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


def compute_manifest_diff(old_manifest: dict[str, Any], new_manifest: dict[str, Any]) -> dict[str, Any]:
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
                (t for t in old_manifest.get("tools", []) if t["name"] == new_tool["name"]),
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
                (r for r in old_manifest.get("resources", []) if r["name"] == new_resource["name"]),
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
                (p for p in old_manifest.get("prompts", []) if p["name"] == new_prompt["name"]),
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
        self.shared_files = {}
        self.import_map = {}

    def generate(self) -> None:
        """Generate the FastMCP application code."""
        # Parse the project and build the manifest
        with console.status("Analyzing project components..."):
            self.components = parse_project(self.project_path)
            self.manifest = build_manifest(self.project_path, self.settings)

            # Find shared Python files and build import map
            from golf.core.parser import parse_shared_files

            self.shared_files = parse_shared_files(self.project_path)
            self.import_map = build_import_map(self.project_path, self.shared_files)

        # Create output directory structure
        with console.status("Creating directory structure..."):
            self._create_directory_structure()

        # Generate code for all components
        tasks = [
            ("Generating tools", self._generate_tools),
            ("Generating resources", self._generate_resources),
            ("Generating prompts", self._generate_prompts),
            ("Generating server entry point", self._generate_server),
        ]

        for description, func in tasks:
            console.print(get_status_text("generating", description))
            func()

        # Get relative path for display
        try:
            output_dir_display = self.output_dir.relative_to(Path.cwd())
        except (ValueError, FileNotFoundError, OSError):
            # ValueError: paths don't have a common base
            # FileNotFoundError/OSError: current directory was deleted
            output_dir_display = self.output_dir

        # Show success message with output directory
        console.print()
        console.print(get_status_text("success", f"Build completed successfully in {output_dir_display}"))

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
        # Process shared files directly in the components directory
        self._process_shared_files()

    def _process_shared_files(self) -> None:
        """Process and transform shared Python files in the components directory
        structure."""
        # Process all shared files
        for module_path_str, shared_file in self.shared_files.items():
            # Convert module path to Path object (e.g., "tools/weather/helpers")
            module_path = Path(module_path_str)

            # Determine the component type
            component_type = None
            for part in module_path.parts:
                if part in ["tools", "resources", "prompts"]:
                    component_type = part
                    break

            if not component_type:
                continue

            # Calculate target directory in components structure
            rel_to_component = module_path.relative_to(component_type)
            target_dir = self.output_dir / "components" / component_type / rel_to_component.parent

            # Create directory if it doesn't exist
            target_dir.mkdir(parents=True, exist_ok=True)

            # Create the shared file in the target directory (preserve original filename)
            target_file = target_dir / shared_file.name

            # Use transformer to process the file
            transform_component(
                component=None,
                output_file=target_file,
                project_path=self.project_path,
                import_map=self.import_map,
                source_file=shared_file,
            )

    def _generate_tools(self) -> None:
        """Generate code for all tools."""
        tools_dir = self.output_dir / "components" / "tools"

        for tool in self.components.get(ComponentType.TOOL, []):
            # Get the tool directory structure
            rel_path = Path(tool.file_path).relative_to(self.project_path)
            if not rel_path.is_relative_to(Path(self.settings.tools_dir)):
                console.print(f"[yellow]Warning: Tool {tool.name} is not in the tools directory[/yellow]")
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
                console.print(f"[yellow]Warning: Resource {resource.name} is not in the resources directory[/yellow]")
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
            transform_component(resource, output_file, self.project_path, self.import_map)

    def _generate_prompts(self) -> None:
        """Generate code for all prompts."""
        prompts_dir = self.output_dir / "components" / "prompts"

        for prompt in self.components.get(ComponentType.PROMPT, []):
            # Get the prompt directory structure
            rel_path = Path(prompt.file_path).relative_to(self.project_path)
            if not rel_path.is_relative_to(Path(self.settings.prompts_dir)):
                console.print(f"[yellow]Warning: Prompt {prompt.name} is not in the prompts directory[/yellow]")
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
            config["endpoint_path"] = "/mcp/"  # Default MCP path for FastMCP

        return config

    def _is_resource_template(self, component: ParsedComponent) -> bool:
        """Check if a resource component is a template (has URI parameters).

        Args:
            component: The parsed component to check

        Returns:
            True if the resource has URI parameters, False otherwise
        """
        return (
            component.type == ComponentType.RESOURCE
            and component.parameters is not None
            and len(component.parameters) > 0
        )

    def _generate_server(self) -> None:
        """Generate the main server entry point."""
        server_file = self.output_dir / "server.py"

        # Get auth components
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
            "from fastmcp.tools import Tool",
            "from fastmcp.resources import Resource, ResourceTemplate",
            "from fastmcp.prompts import Prompt",
            "import os",
            "import sys",
            "from dotenv import load_dotenv",
            "import logging",
            "",
            "# Suppress FastMCP INFO logs",
            "logging.getLogger('FastMCP').setLevel(logging.ERROR)",
            "logging.getLogger('mcp').setLevel(logging.ERROR)",
            "",
            "# Golf utilities for MCP features (available for tool functions)",
            "# from golf.utilities import elicit, sample, get_current_context",
            "",
        ]

        # Add auth imports if auth is configured
        if auth_components.get("has_auth"):
            imports.extend(auth_components["imports"])
            imports.append("")

        # Add OpenTelemetry imports if enabled
        if self.settings.opentelemetry_enabled:
            imports.extend(generate_telemetry_imports())

        # Add metrics imports if enabled
        if self.settings.metrics_enabled:
            from golf.core.builder_metrics import (
                generate_metrics_imports,
                generate_metrics_instrumentation,
                generate_session_tracking,
            )

            imports.extend(generate_metrics_imports())
            imports.extend(generate_metrics_instrumentation())
            imports.extend(generate_session_tracking())

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
                            parent_path = str(rel_to_tools.parent).replace("\\", ".").replace("/", ".")
                            import_path = f"components.tools.{parent_path}"
                        else:
                            import_path = "components.tools"
                    except ValueError:
                        import_path = "components.tools"
                elif component_type == ComponentType.RESOURCE:
                    try:
                        rel_to_resources = rel_path.relative_to(self.settings.resources_dir)
                        # Handle nested directories properly
                        if rel_to_resources.parent != Path("."):
                            parent_path = str(rel_to_resources.parent).replace("\\", ".").replace("/", ".")
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
                            parent_path = str(rel_to_prompts.parent).replace("\\", ".").replace("/", ".")
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
                        if hasattr(component, "entry_function") and component.entry_function
                        else "export"
                    )

                    registration += (
                        f"\n_wrapped_func = instrument_{component_type.value}("
                        f"{full_module_path}.{entry_func}, '{component.name}')"
                    )

                    if component_type == ComponentType.TOOL:
                        registration += (
                            f"\n_tool = Tool.from_function(_wrapped_func, "
                            f'name="{component.name}", '
                            f'description="{component.docstring or ""}")'
                        )
                        # Add annotations if present
                        if hasattr(component, "annotations") and component.annotations:
                            registration += f".with_annotations({component.annotations})"
                        registration += "\nmcp.add_tool(_tool)"
                    elif component_type == ComponentType.RESOURCE:
                        if self._is_resource_template(component):
                            registration += (
                                f"\n_template = ResourceTemplate.from_function(_wrapped_func, "
                                f'uri_template="{component.uri_template}", name="{component.name}", '
                                f'description="{component.docstring or ""}")\n'
                                f"mcp.add_template(_template)"
                            )
                        else:
                            registration += (
                                f"\n_resource = Resource.from_function(_wrapped_func, "
                                f'uri="{component.uri_template}", name="{component.name}", '
                                f'description="{component.docstring or ""}")\n'
                                f"mcp.add_resource(_resource)"
                            )
                    else:  # PROMPT
                        registration += (
                            f"\n_prompt = Prompt.from_function(_wrapped_func, "
                            f'name="{component.name}", '
                            f'description="{component.docstring or ""}")\n'
                            f"mcp.add_prompt(_prompt)"
                        )
                elif self.settings.metrics_enabled:
                    # Use metrics instrumentation
                    registration = f"# Register the {component_type.value} '{component.name}' with metrics"
                    entry_func = (
                        component.entry_function
                        if hasattr(component, "entry_function") and component.entry_function
                        else "export"
                    )

                    registration += (
                        f"\n_wrapped_func = instrument_{component_type.value}("
                        f"{full_module_path}.{entry_func}, '{component.name}')"
                    )

                    if component_type == ComponentType.TOOL:
                        registration += (
                            f"\n_tool = Tool.from_function(_wrapped_func, "
                            f'name="{component.name}", '
                            f'description="{component.docstring or ""}")'
                        )
                        # Add annotations if present
                        if hasattr(component, "annotations") and component.annotations:
                            registration += f".with_annotations({component.annotations})"
                        registration += "\nmcp.add_tool(_tool)"
                    elif component_type == ComponentType.RESOURCE:
                        if self._is_resource_template(component):
                            registration += (
                                f"\n_template = ResourceTemplate.from_function(_wrapped_func, "
                                f'uri_template="{component.uri_template}", name="{component.name}", '
                                f'description="{component.docstring or ""}")\n'
                                f"mcp.add_template(_template)"
                            )
                        else:
                            registration += (
                                f"\n_resource = Resource.from_function(_wrapped_func, "
                                f'uri="{component.uri_template}", name="{component.name}", '
                                f'description="{component.docstring or ""}")\n'
                                f"mcp.add_resource(_resource)"
                            )
                    else:  # PROMPT
                        registration += (
                            f"\n_prompt = Prompt.from_function(_wrapped_func, "
                            f'name="{component.name}", '
                            f'description="{component.docstring or ""}")\n'
                            f"mcp.add_prompt(_prompt)"
                        )
                else:
                    # Standard registration without telemetry
                    if component_type == ComponentType.TOOL:
                        registration = f"# Register the tool '{component.name}' from {full_module_path}"

                        # Use the entry_function if available, otherwise try the
                        # export variable
                        if hasattr(component, "entry_function") and component.entry_function:
                            registration += (
                                f"\n_tool = Tool.from_function({full_module_path}.{component.entry_function}"
                            )
                        else:
                            registration += f"\n_tool = Tool.from_function({full_module_path}.export"

                        # Add the name parameter
                        registration += f', name="{component.name}"'

                        # Add description from docstring
                        if component.docstring:
                            # Escape any quotes in the docstring
                            escaped_docstring = component.docstring.replace('"', '\\"')
                            registration += f', description="{escaped_docstring}"'

                        registration += ")"

                        # Add annotations if present
                        if hasattr(component, "annotations") and component.annotations:
                            registration += f"\n_tool = _tool.with_annotations({component.annotations})"

                        registration += "\nmcp.add_tool(_tool)"

                    elif component_type == ComponentType.RESOURCE:
                        if self._is_resource_template(component):
                            registration = (
                                f"# Register the resource template '{component.name}' from {full_module_path}"
                            )

                            # Use the entry_function if available, otherwise try the
                            # export variable
                            if hasattr(component, "entry_function") and component.entry_function:
                                registration += (
                                    f"\n_template = ResourceTemplate.from_function("
                                    f"{full_module_path}.{component.entry_function}, "
                                    f'uri_template="{component.uri_template}"'
                                )
                            else:
                                registration += (
                                    f"\n_template = ResourceTemplate.from_function("
                                    f"{full_module_path}.export, "
                                    f'uri_template="{component.uri_template}"'
                                )

                            # Add the name parameter
                            registration += f', name="{component.name}"'

                            # Add description from docstring
                            if component.docstring:
                                # Escape any quotes in the docstring
                                escaped_docstring = component.docstring.replace('"', '\\"')
                                registration += f', description="{escaped_docstring}"'

                            registration += ")\nmcp.add_template(_template)"
                        else:
                            registration = f"# Register the resource '{component.name}' from {full_module_path}"

                            # Use the entry_function if available, otherwise try the
                            # export variable
                            if hasattr(component, "entry_function") and component.entry_function:
                                registration += (
                                    f"\n_resource = Resource.from_function("
                                    f"{full_module_path}.{component.entry_function}, "
                                    f'uri="{component.uri_template}"'
                                )
                            else:
                                registration += (
                                    f"\n_resource = Resource.from_function("
                                    f"{full_module_path}.export, "
                                    f'uri="{component.uri_template}"'
                                )

                            # Add the name parameter
                            registration += f', name="{component.name}"'

                            # Add description from docstring
                            if component.docstring:
                                # Escape any quotes in the docstring
                                escaped_docstring = component.docstring.replace('"', '\\"')
                                registration += f', description="{escaped_docstring}"'

                            registration += ")\nmcp.add_resource(_resource)"

                    else:  # PROMPT
                        registration = f"# Register the prompt '{component.name}' from {full_module_path}"

                        # Use the entry_function if available, otherwise try the
                        # export variable
                        if hasattr(component, "entry_function") and component.entry_function:
                            registration += (
                                f"\n_prompt = Prompt.from_function({full_module_path}.{component.entry_function}"
                            )
                        else:
                            registration += f"\n_prompt = Prompt.from_function({full_module_path}.export"

                        # Add the name parameter
                        registration += f', name="{component.name}"'

                        # Add description from docstring
                        if component.docstring:
                            # Escape any quotes in the docstring
                            escaped_docstring = component.docstring.replace('"', '\\"')
                            registration += f', description="{escaped_docstring}"'

                        registration += ")\nmcp.add_prompt(_prompt)"

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

        # Add stateless HTTP parameter if enabled
        if self.settings.stateless_http:
            mcp_constructor_args.append("stateless_http=True")

        # Add OpenTelemetry parameters if enabled
        if self.settings.opentelemetry_enabled:
            mcp_constructor_args.append("lifespan=telemetry_lifespan")

        mcp_instance_line = f"mcp = FastMCP({', '.join(mcp_constructor_args)})"
        server_code_lines.append(mcp_instance_line)
        server_code_lines.append("")

        # Add early telemetry initialization if enabled (before component registration)
        early_telemetry_init = []
        if self.settings.opentelemetry_enabled:
            early_telemetry_init.extend(
                [
                    "# Initialize telemetry early to ensure instrumentation works",
                    "from golf.telemetry.instrumentation import init_telemetry, set_detailed_tracing",
                    f'init_telemetry("{self.settings.name}")',
                    f"set_detailed_tracing({self.settings.detailed_tracing})",
                    "",
                ]
            )

        # Add metrics initialization if enabled
        early_metrics_init = []
        if self.settings.metrics_enabled:
            from golf.core.builder_metrics import generate_metrics_initialization

            early_metrics_init.extend(generate_metrics_initialization(self.settings.name))

        # Main entry point with transport-specific app initialization
        main_code = [
            'if __name__ == "__main__":',
            "    from rich.console import Console",
            "    from rich.panel import Panel",
            "    console = Console()",
            "    # Get configuration from environment variables or use defaults",
            '    host = os.environ.get("HOST", "localhost")',
            '    port = int(os.environ.get("PORT", 3000))',
            f'    transport_to_run = "{self.settings.transport}"',
            "",
        ]

        main_code.append("")

        # Transport-specific run methods
        if self.settings.transport == "sse":
            # Check if we need middleware for SSE
            middleware_setup = []
            middleware_list = []

            api_key_config = get_api_key_config()
            if auth_components.get("has_auth") and api_key_config:
                middleware_setup.append("    from starlette.middleware import Middleware")
                middleware_list.append("Middleware(ApiKeyMiddleware)")

            # Add metrics middleware if enabled
            if self.settings.metrics_enabled:
                middleware_setup.append("    from starlette.middleware import Middleware")
                middleware_list.append("Middleware(MetricsMiddleware)")

            # Add OpenTelemetry middleware if enabled
            if self.settings.opentelemetry_enabled:
                middleware_setup.append("    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware")
                middleware_setup.append("    from starlette.middleware import Middleware")
                middleware_list.append("Middleware(OpenTelemetryMiddleware)")

            if middleware_setup:
                main_code.extend(middleware_setup)
                main_code.append(f"    middleware = [{', '.join(middleware_list)}]")
                main_code.append("")
                main_code.extend(
                    [
                        "    # Run SSE server with middleware using FastMCP's run method",
                        f'    mcp.run(transport="sse", host=host, port=port, '
                        f'path="{endpoint_path}", log_level="info", '
                        f"middleware=middleware, show_banner=False)",
                    ]
                )
            else:
                main_code.extend(
                    [
                        "    # Run SSE server using FastMCP's run method",
                        f'    mcp.run(transport="sse", host=host, port=port, '
                        f'path="{endpoint_path}", log_level="info", '
                        f"show_banner=False)",
                    ]
                )

        elif self.settings.transport in ["streamable-http", "http"]:
            # Check if we need middleware for streamable-http
            middleware_setup = []
            middleware_list = []

            api_key_config = get_api_key_config()
            if auth_components.get("has_auth") and api_key_config:
                middleware_setup.append("    from starlette.middleware import Middleware")
                middleware_list.append("Middleware(ApiKeyMiddleware)")

            # Add metrics middleware if enabled
            if self.settings.metrics_enabled:
                middleware_setup.append("    from starlette.middleware import Middleware")
                middleware_list.append("Middleware(MetricsMiddleware)")

            # Add OpenTelemetry middleware if enabled
            if self.settings.opentelemetry_enabled:
                middleware_setup.append("    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware")
                middleware_setup.append("    from starlette.middleware import Middleware")
                middleware_list.append("Middleware(OpenTelemetryMiddleware)")

            if middleware_setup:
                main_code.extend(middleware_setup)
                main_code.append(f"    middleware = [{', '.join(middleware_list)}]")
                main_code.append("")
                main_code.extend(
                    [
                        "    # Run HTTP server with middleware using FastMCP's run method",
                        f'    mcp.run(transport="streamable-http", host=host, '
                        f'port=port, path="{endpoint_path}", log_level="info", '
                        f"middleware=middleware, show_banner=False)",
                    ]
                )
            else:
                main_code.extend(
                    [
                        "    # Run HTTP server using FastMCP's run method",
                        f'    mcp.run(transport="streamable-http", host=host, '
                        f'port=port, path="{endpoint_path}", log_level="info", '
                        f"show_banner=False)",
                    ]
                )
        else:
            # For stdio transport, use mcp.run()
            main_code.extend(["    # Run with stdio transport", '    mcp.run(transport="stdio", show_banner=False)'])

        # Add metrics route if enabled
        metrics_route_code = []
        if self.settings.metrics_enabled:
            from golf.core.builder_metrics import generate_metrics_route

            metrics_route_code = generate_metrics_route(self.settings.metrics_path)

        # Add health check route if enabled
        health_check_code = []
        if self.settings.health_check_enabled:
            health_check_code = [
                "# Add health check route",
                "@mcp.custom_route('" + self.settings.health_check_path + '\', methods=["GET"])',
                "async def health_check(request: Request) -> PlainTextResponse:",
                '    """Health check endpoint for Kubernetes and load balancers."""',
                (f'    return PlainTextResponse("{self.settings.health_check_response}")'),
                "",
            ]

        # Combine all sections
        # Order: imports, env_section, auth_setup, server_code (mcp init),
        # early_telemetry_init, early_metrics_init, component_registrations,
        # metrics_route_code, health_check_code, main_code (run block)
        code = "\n".join(
            imports
            + env_section
            + auth_setup_code
            + server_code_lines
            + early_telemetry_init
            + early_metrics_init
            + component_registrations
            + metrics_route_code
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
    # Load Golf credentials from .env for build operations (platform registration, etc.)
    # This happens regardless of copy_env setting to ensure build process works
    from dotenv import load_dotenv

    project_env_file = project_path / ".env"
    if project_env_file.exists():
        # Load GOLF_* variables for build process
        load_dotenv(project_env_file, override=False)

        # Only log if we actually found the specific Golf platform credentials
        has_api_key = "GOLF_API_KEY" in os.environ
        has_server_id = "GOLF_SERVER_ID" in os.environ
        if has_api_key and has_server_id:
            console.print("[dim]Loaded Golf credentials for build operations[/dim]")

    # Execute auth.py if it exists (for authentication configuration)
    # Also support legacy pre_build.py for backward compatibility
    auth_path = project_path / "auth.py"
    legacy_path = project_path / "pre_build.py"

    config_path = None
    if auth_path.exists():
        config_path = auth_path
    elif legacy_path.exists():
        config_path = legacy_path
        console.print("[yellow]Warning: pre_build.py is deprecated. Rename to auth.py[/yellow]")

    if config_path:
        # Save the current directory and path - handle case where cwd might be invalid
        try:
            original_dir = os.getcwd()
        except (FileNotFoundError, OSError):
            # Current directory might have been deleted by previous operations,
            # use project_path as fallback
            original_dir = str(project_path)
            os.chdir(original_dir)
        original_path = sys.path.copy()

        try:
            # Change to the project directory and add it to Python path
            os.chdir(project_path)
            sys.path.insert(0, str(project_path))

            # Execute the auth configuration script
            with open(config_path) as f:
                script_content = f.read()

            # Print the first few lines for debugging
            "\n".join(script_content.split("\n")[:5]) + "\n..."

            # Use exec to run the script as a module
            code = compile(script_content, str(config_path), "exec")
            exec(code, {})

        except Exception as e:
            console.print(f"[red]Error executing {config_path.name}: {str(e)}[/red]")
            import traceback

            console.print(f"[red]{traceback.format_exc()}[/red]")

            # Track detailed error for auth.py execution failures
            try:
                from golf.core.telemetry import track_detailed_error

                track_detailed_error(
                    "build_auth_failed",
                    e,
                    context=f"Executing {config_path.name} configuration script",
                    operation="auth_execution",
                    additional_props={
                        "file_path": str(config_path.relative_to(project_path)),
                        "build_env": build_env,
                    },
                )
            except Exception:
                # Don't let telemetry errors break the build
                pass
        finally:
            # Always restore original directory and path, even if an exception occurred
            try:
                os.chdir(original_dir)
                sys.path = original_path
            except Exception:
                # If we can't restore the directory, at least try to reset the path
                sys.path = original_path

    # Clear the output directory if it exists
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)  # Ensure output_dir exists after clearing

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
                    "[yellow]Warning: python-dotenv is not installed. "
                    "Cannot read existing .env file for rich merging. "
                    "Copying directly.[/yellow]"
                )
                try:
                    shutil.copy(project_env_file, env_file_path)
                    # If direct copy happens, re-read for step 2 & 3 to respect
                    # its content
                    if env_file_path.exists():
                        from dotenv import dotenv_values

                        env_vars_to_write.update(dotenv_values(env_file_path))  # Read what was copied
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not copy project .env file: {e}[/yellow]")
            except Exception as e:
                console.print(f"[yellow]Warning: Error reading project .env file content: {e}[/yellow]")

    # 2. Apply Golf's OTel default exporter setting if OTEL_TRACES_EXPORTER
    # is not already set
    if (
        settings.opentelemetry_enabled
        and settings.opentelemetry_default_exporter
        and "OTEL_TRACES_EXPORTER" not in env_vars_to_write
    ):
        env_vars_to_write["OTEL_TRACES_EXPORTER"] = settings.opentelemetry_default_exporter

    # 3. Apply Golf's project name as OTEL_SERVICE_NAME if not already set
    # (Ensures service name defaults to project name if not specified in user's .env)
    if settings.opentelemetry_enabled and settings.name and "OTEL_SERVICE_NAME" not in env_vars_to_write:
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
                        processed_value = value.replace("\\", "\\\\")  # Escape backslashes
                        processed_value = processed_value.replace('"', '\\"')  # Escape double quotes
                        if " " in value or "#" in value or "\n" in value or '"' in value or "'" in value:
                            f.write(f'{key}="{processed_value}"\n')
                        else:
                            f.write(f"{key}={processed_value}\n")
                    else:  # For non-string values, write directly
                        f.write(f"{key}={value}\n")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not write .env file to output directory: {e}[/yellow]")
    # --- END Enhanced .env handling ---

    # Show what we're building, with environment info
    create_build_header(settings.name, build_env, console)

    # Generate the code
    generator = CodeGenerator(project_path, settings, output_dir, build_env=build_env, copy_env=copy_env)
    generator.generate()

    # Platform registration (only for prod builds)
    if build_env == "prod":
        console.print()
        status_msg = f"[{GOLF_BLUE}]{STATUS_ICONS['platform']} Registering with Golf platform and updating resources...[/{GOLF_BLUE}]"
        with console.status(status_msg):
            import asyncio

            try:
                from golf.core.platform import register_project_with_platform

                success = asyncio.run(
                    register_project_with_platform(
                        project_path=project_path,
                        settings=settings,
                        components=generator.components,
                    )
                )

                if success:
                    console.print(get_status_text("success", "Platform registration completed"))
                # If success is False, the platform module already printed appropriate warnings
            except ImportError:
                console.print(get_status_text("warning", "Platform registration module not available"))
            except Exception as e:
                console.print(get_status_text("warning", f"Platform registration failed: {e}"))
                console.print("[dim]Tip: Ensure GOLF_API_KEY and GOLF_SERVER_ID are available in your .env file[/dim]")

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

    # Always copy the auth module so it's available
    auth_dir = output_dir / "golf" / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py with needed exports
    with open(auth_dir / "__init__.py", "w") as f:
        f.write(
            """\"\"\"Auth module for GolfMCP.\"\"\"

# Legacy ProviderConfig removed in Golf 0.2.x - use modern auth configurations
# Legacy OAuth imports removed in Golf 0.2.x - use FastMCP 2.11+ auth providers
from golf.auth.helpers import get_provider_token, extract_token_from_header, get_api_key, set_api_key
from golf.auth.api_key import configure_api_key, get_api_key_config
from golf.auth.factory import create_auth_provider
from golf.auth.providers import RemoteAuthConfig, JWTAuthConfig, StaticTokenConfig, OAuthServerConfig
"""
        )

    # Copy auth modules required for Golf 0.2.x
    for module in ["helpers.py", "api_key.py", "factory.py", "providers.py"]:
        src_file = Path(__file__).parent.parent.parent / "golf" / "auth" / module
        dst_file = auth_dir / module

        if src_file.exists():
            shutil.copy(src_file, dst_file)
        else:
            console.print(f"[yellow]Warning: Could not find {src_file} to copy[/yellow]")

    # Copy telemetry module if OpenTelemetry is enabled
    if settings.opentelemetry_enabled:
        telemetry_dir = output_dir / "golf" / "telemetry"
        telemetry_dir.mkdir(parents=True, exist_ok=True)

        # Copy telemetry __init__.py
        src_init = Path(__file__).parent.parent.parent / "golf" / "telemetry" / "__init__.py"
        dst_init = telemetry_dir / "__init__.py"
        if src_init.exists():
            shutil.copy(src_init, dst_init)

        # Copy instrumentation module
        src_instrumentation = Path(__file__).parent.parent.parent / "golf" / "telemetry" / "instrumentation.py"
        dst_instrumentation = telemetry_dir / "instrumentation.py"
        if src_instrumentation.exists():
            shutil.copy(src_instrumentation, dst_instrumentation)
        else:
            console.print("[yellow]Warning: Could not find telemetry instrumentation module[/yellow]")

    # Check if auth routes need to be added
    if is_auth_configured() or get_api_key_config():
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
                    server_code_content[:app_pos] + auth_routes_code + "\n\n" + server_code_content[app_pos:]
                )

                # Format with black before writing
                try:
                    final_code_to_write = black.format_str(modified_code, mode=black.Mode())
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


# Legacy function removed - replaced by parse_shared_files in parser module


# Updated to handle any shared file, not just common.py files
def build_import_map(project_path: Path, shared_files: dict[str, Path]) -> dict[str, str]:
    """Build a mapping of import paths to their new locations in the build output.

    This maps from original relative import paths to absolute import paths
    in the components directory structure.

    Args:
        project_path: Path to the project root
        shared_files: Dictionary mapping module paths to shared file paths
    """
    import_map = {}

    for module_path_str, file_path in shared_files.items():
        # Convert module path to Path object (e.g., "tools/weather/helpers" -> Path("tools/weather/helpers"))
        module_path = Path(module_path_str)

        # Get the component type (tools, resources, prompts)
        component_type = None
        for part in module_path.parts:
            if part in ["tools", "resources", "prompts"]:
                component_type = part
                break

        if not component_type:
            continue

        # Calculate the relative path within the component type
        try:
            rel_to_component = module_path.relative_to(component_type)
            # Create the new import path
            if str(rel_to_component) == ".":
                # This shouldn't happen for individual files, but handle it
                new_path = f"components.{component_type}"
            else:
                # Replace path separators with dots
                path_parts = str(rel_to_component).replace("\\", "/").split("/")
                new_path = f"components.{component_type}.{'.'.join(path_parts)}"

            # Map the specific shared module
            # e.g., "tools/weather/helpers" -> "components.tools.weather.helpers"
            import_map[module_path_str] = new_path

            # Also map the directory path for relative imports
            # e.g., "tools/weather" -> "components.tools.weather"
            dir_path_str = str(module_path.parent)
            if dir_path_str != "." and dir_path_str not in import_map:
                dir_rel_to_component = module_path.parent.relative_to(component_type)
                if str(dir_rel_to_component) == ".":
                    dir_new_path = f"components.{component_type}"
                else:
                    dir_path_parts = str(dir_rel_to_component).replace("\\", "/").split("/")
                    dir_new_path = f"components.{component_type}.{'.'.join(dir_path_parts)}"
                import_map[dir_path_str] = dir_new_path

        except ValueError:
            continue

    return import_map
