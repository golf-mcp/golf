"""Builder for generating FastMCP manifests from parsed components."""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import black
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

from golf.core.config import Settings
from golf.core.parser import (
    ComponentType, 
    ParsedComponent, 
    parse_project, 
)
from golf.core.transformer import transform_component
from golf.core.builder_auth import generate_auth_code, generate_auth_routes
from golf.auth import get_auth_config
from golf.auth import get_access_token
from golf.core.builder_telemetry import (
    generate_otel_lifespan_code, 
    generate_otel_instrumentation_code, 
    get_otel_dependencies
)

console = Console()


class ManifestBuilder:
    """Builds FastMCP manifest from parsed components."""
    
    def __init__(self, project_path: Path, settings: Settings):
        """Initialize the manifest builder.
        
        Args:
            project_path: Path to the project root
            settings: Project settings
        """
        self.project_path = project_path
        self.settings = settings
        self.components: Dict[ComponentType, List[ParsedComponent]] = {}
        self.manifest: Dict[str, Any] = {
            "name": settings.name,
            "description": settings.description or "",
            "tools": [],
            "resources": [],
            "prompts": []
        }
    
    def build(self) -> Dict[str, Any]:
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
                    "$schema": "http://json-schema.org/draft-07/schema#"
                },
                "annotations": {
                    "title": component.name.replace('-', ' ').title()
                },
                "entry_function": component.entry_function
            }
            
            # Include required fields if they exist
            if required_fields:
                tool_schema["inputSchema"]["required"] = required_fields
            
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
                "entry_function": component.entry_function
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
                "entry_function": component.entry_function
            }
            
            # If the prompt has parameters, include them
            if component.parameters:
                arguments = []
                for param in component.parameters:
                    arguments.append({
                        "name": param,
                        "required": True  # Default to required
                    })
                prompt_schema["arguments"] = arguments
            
            # Add the prompt to the manifest
            self.manifest["prompts"].append(prompt_schema)
    
    def save_manifest(self, output_path: Optional[Path] = None) -> Path:
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


def build_manifest(project_path: Path, settings: Settings) -> Dict[str, Any]:
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
    old_manifest: Dict[str, Any], new_manifest: Dict[str, Any]
) -> Dict[str, Any]:
    """Compute the difference between two manifests.
    
    Args:
        old_manifest: Previous manifest
        new_manifest: New manifest
        
    Returns:
        Dictionary describing the changes
    """
    diff = {
        "tools": {
            "added": [],
            "removed": [],
            "changed": []
        },
        "resources": {
            "added": [],
            "removed": [],
            "changed": []
        },
        "prompts": {
            "added": [],
            "removed": [],
            "changed": []
        }
    }
    
    # Helper function to extract names from a list of components
    def extract_names(components: List[Dict[str, Any]]) -> Set[str]:
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
            old_tool = next((t for t in old_manifest.get("tools", []) if t["name"] == new_tool["name"]), None)
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
            old_resource = next((r for r in old_manifest.get("resources", []) if r["name"] == new_resource["name"]), None)
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
            old_prompt = next((p for p in old_manifest.get("prompts", []) if p["name"] == new_prompt["name"]), None)
            if old_prompt and json.dumps(old_prompt) != json.dumps(new_prompt):
                diff["prompts"]["changed"].append(new_prompt["name"])
    
    return diff


def has_changes(diff: Dict[str, Any]) -> bool:
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
    
    def __init__(self, project_path: Path, settings: Settings, output_dir: Path, build_env: str = "prod", copy_env: bool = False):
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
        console.print(f"[bold green]✓[/bold green] Build completed successfully in [bold]{output_dir_display}[/bold]")
    
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
            target_dir = self.output_dir / "components" / component_type / rel_to_component
            
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
                source_file=common_file
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
            transform_component(
                tool,
                output_file,
                self.project_path,
                self.import_map
            )
    
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
            transform_component(
                resource,
                output_file,
                self.project_path,
                self.import_map
            )
    
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
            transform_component(
                prompt,
                output_file,
                self.project_path,
                self.import_map
            )
    
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
            config["endpoint_path"] = "/sse" # Default SSE path for FastMCP
        elif transport_type == "stdio":
            config["endpoint_path"] = "" # No HTTP endpoint
        else:
            # Default to streamable-http
            config["endpoint_path"] = "/mcp" # Default MCP path for FastMCP
            
        return config
    
    def _generate_server(self) -> None:
        """Generate the main server entry point."""
        server_file = self.output_dir / "server.py"
        
        # Create imports section
        imports = [
            "from fastmcp import FastMCP",
            "import os",
            "import sys",
            "from dotenv import load_dotenv",
            ""
        ]
        
        # For imports
        if self.settings.opentelemetry_enabled:
            imports.extend([
                "# OpenTelemetry imports",
                "from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware",
                "from starlette.middleware import Middleware",
                # otel_lifespan function will be defined from generate_otel_lifespan_code
            ])
        imports.append("") # Add blank line after all component type imports or OTel imports
        
        # Add imports section for different transport methods
        if self.settings.transport == "sse":
            imports.append("import uvicorn")
            imports.append("from fastmcp.server.http import create_sse_app")
        elif self.settings.transport != "stdio":
            imports.append("import uvicorn")
                
        # Create a new FastMCP instance for the server
        server_code_lines = ["# Create FastMCP server"]
        mcp_constructor_args = [f'"{self.settings.name}"']

        mcp_instance_line = f"mcp = FastMCP({', '.join(mcp_constructor_args)})"
        server_code_lines.append(mcp_instance_line)
        server_code_lines.append("")
        
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
                if component_type == ComponentType.TOOL:
                    registration = f"# Register the tool '{component.name}' from {full_module_path}"
                    
                    # Use the entry_function if available, otherwise try the export variable
                    if hasattr(component, "entry_function") and component.entry_function:
                        registration += f"\nmcp.add_tool({full_module_path}.{component.entry_function}"
                    else:
                        registration += f"\nmcp.add_tool({full_module_path}.export"
                    
                    # Add the name parameter
                    registration += f", name=\"{component.name}\""
                    
                    # Add description from docstring
                    if component.docstring:
                        # Escape any quotes in the docstring
                        escaped_docstring = component.docstring.replace("\"", "\\\"")
                        registration += f", description=\"{escaped_docstring}\""
                    registration += ")"

                elif component_type == ComponentType.RESOURCE:
                    registration = f"# Register the resource '{component.name}' from {full_module_path}"
                    
                    # Use the entry_function if available, otherwise try the export variable
                    if hasattr(component, "entry_function") and component.entry_function:
                        registration += f"\nmcp.add_resource_fn({full_module_path}.{component.entry_function}, uri=\"{component.uri_template}\""
                    else:
                        registration += f"\nmcp.add_resource_fn({full_module_path}.export, uri=\"{component.uri_template}\""
                    
                    # Add the name parameter
                    registration += f", name=\"{component.name}\""
                        
                    # Add description from docstring
                    if component.docstring:
                        # Escape any quotes in the docstring
                        escaped_docstring = component.docstring.replace("\"", "\\\"")
                        registration += f", description=\"{escaped_docstring}\""
                    registration += ")"

                else:  # PROMPT
                    registration = f"# Register the prompt '{component.name}' from {full_module_path}"
                    
                    # Use the entry_function if available, otherwise try the export variable
                    if hasattr(component, "entry_function") and component.entry_function:
                        registration += f"\nmcp.add_prompt({full_module_path}.{component.entry_function}"
                    else:
                        registration += f"\nmcp.add_prompt({full_module_path}.export"
                    
                    # Add the name parameter
                    registration += f", name=\"{component.name}\""
                        
                    # Add description from docstring
                    if component.docstring:
                        # Escape any quotes in the docstring
                        escaped_docstring = component.docstring.replace("\"", "\\\"")
                        registration += f", description=\"{escaped_docstring}\""
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
            ""
        ]

        # After env_section, add OpenTelemetry lifespan code
        otel_definitions_code = []
        otel_instrumentation_application_code = [] # For instrumentation that runs after mcp is set up

        if self.settings.opentelemetry_enabled:
            otel_definitions_code.append(generate_otel_lifespan_code(
                default_exporter=self.settings.opentelemetry_default_exporter,
                project_name=self.settings.name
            ))
            otel_definitions_code.append("")  # Add blank line

            # Prepare instrumentation code to be added after component registration
            otel_instrumentation_application_code.append("# Apply OpenTelemetry Instrumentation")
            otel_instrumentation_application_code.append(generate_otel_instrumentation_code())
            otel_instrumentation_application_code.append("")

        # Main entry point with transport-specific app initialization
        main_code = [
            "if __name__ == \"__main__\":",
            "    from rich.console import Console",
            "    from rich.panel import Panel",
            "    console = Console()",
            "    # Get configuration from environment variables or use defaults",
            "    host = os.environ.get(\"HOST\", \"127.0.0.1\")",
            "    port = int(os.environ.get(\"PORT\", 3000))",
            f"    transport_to_run = \"{self.settings.transport}\"",
            ""
        ]
        
        # Add startup message
        if self.settings.transport != "stdio":
            main_code.append(f'    console.print(Panel.fit(f"[bold green]{{mcp.name}}[/bold green]\\n[dim]Running on http://{{host}}:{{port}}{endpoint_path} with transport \\"{{transport_to_run}}\\" (environment: {self.build_env})[/dim]", border_style="green"))')
        else:
            main_code.append(f'    console.print(Panel.fit(f"[bold green]{{mcp.name}}[/bold green]\\n[dim]Running with transport \\"{{transport_to_run}}\\" (environment: {self.build_env})[/dim]", border_style="green"))')
            
        main_code.append("")
        
        # Transport-specific run methods
        if self.settings.transport == "sse":
            main_code.extend([
                "    # For SSE, FastMCP's run method handles auth integration better",
                "    print(f\"[Server Runner] Using mcp.run() for SSE transport with host={host}, port={port}\", file=sys.stderr)",
                "    mcp.run(transport=\"sse\", host=host, port=port, log_level=\"debug\")"
            ])
        elif self.settings.transport == "streamable-http":
            main_code.extend([
                "    # Create HTTP app and run with uvicorn",
                "    print(f\"[Server Runner] Starting streamable-http transport with host={host}, port={port}\", file=sys.stderr)",
                "    app = mcp.http_app()",
                "    uvicorn.run(app, host=host, port=port, log_level=\"debug\")"
            ])
        else:
            # For stdio transport, use mcp.run()
            main_code.extend([
                "    # Run with stdio transport",
                "    print(f\"[Server Runner] Starting stdio transport\", file=sys.stderr)",
                "    mcp.run(transport=\"stdio\")"
            ])
        
        # Combine all sections - move env_section to right location
        # Order: imports, env_section, otel_definitions (lifespan func), server_code (mcp init), 
        # component_registrations, otel_instrumentation (wrappers), main_code (run block)
        code = "\n".join(
            imports + 
            env_section + 
            otel_definitions_code + 
            server_code_lines +  # Add back the server_code_lines with constructor
            component_registrations + 
            otel_instrumentation_application_code + # Added instrumentation here
            main_code
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
    copy_env: bool = False
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
            preview = "\n".join(script_content.split("\n")[:5]) + "\n..."
            
            # Use exec to run the script as a module
            code = compile(script_content, str(pre_build_path), 'exec')
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
    
    # Clear the output directory if it exists
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True) # Ensure output_dir exists after clearing
    
    # If dev build and copy_env flag is true, copy .env file from project root to output_dir
    if copy_env: # The build_env string ('dev'/'prod') check can be done in the CLI layer that sets copy_env
        project_env_file = project_path / ".env"
        if project_env_file.exists():
            try:
                shutil.copy(project_env_file, output_dir / ".env")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not copy project .env file: {e}[/yellow]")

    # Show what we're building, with environment info
    console.print(f"[bold]Building [green]{settings.name}[/green] ({build_env} environment)[/bold]")
    
    # Generate the code
    generator = CodeGenerator(
        project_path, 
        settings, 
        output_dir,
        build_env=build_env,
        copy_env=copy_env
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
    provider_config, required_scopes = get_auth_config() # Ensure this is called to check for auth
    if provider_config:
        base_dependencies.extend([
            "pyjwt>=2.0.0",
            "httpx>=0.20.0",
        ])

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
        f.write("""\"\"\"Auth module for GolfMCP.\"\"\"

from golf.auth.provider import ProviderConfig
from golf.auth.oauth import GolfOAuthProvider, create_callback_handler
from golf.auth.helpers import get_access_token, get_provider_token, extract_token_from_header
""")
    
    # Copy provider, oauth, and helper modules
    for module in ["provider.py", "oauth.py", "helpers.py"]:
        src_file = Path(__file__).parent.parent.parent / "golf" / "auth" / module
        dst_file = auth_dir / module
        
        if src_file.exists():
            shutil.copy(src_file, dst_file)
        else:
            console.print(f"[yellow]Warning: Could not find {src_file} to copy[/yellow]")
    
    # Now handle the auth integration if configured
    if provider_config:
        
        # Generate the auth code to inject into server.py
        # The existing call to generate_auth_code.
        # We need to ensure the arguments passed are sensible.
        # server.py determines issuer_url at runtime. generate_auth_code
        # likely uses host/port/https to construct its own version or parts of it.
        
        # Determine protocol for https flag based on runtime logic similar to server.py
        # This is a bit of a guess as settings doesn't explicitly store protocol for generate_auth_code
        # A small inconsistency here if server.py's runtime logic for issuer_url differs significantly
        # from what generate_auth_code expects/builds.
        # For now, let's assume False is okay, or it's handled internally by generate_auth_code
        # based on typical dev environments.
        is_https_proto = False # Default, adjust if settings provide this info for build time

        auth_code_str = generate_auth_code( # Renamed to auth_code_str to avoid confusion
            server_name=settings.name,
            host=settings.host,
            port=settings.port
        )
    else:
        # If auth is not configured, create a basic FastMCP instantiation string
        # This string will then be processed for OTel args like the auth_code_str would be
        auth_code_str = f"mcp = FastMCP('{settings.name}')" 

    # ---- Centralized OpenTelemetry Argument Injection ----
    if settings.opentelemetry_enabled:
        temp_mcp_lines = auth_code_str.split('\n')
        final_mcp_lines = []
        otel_args_injected = False
        for line_content in temp_mcp_lines:
            if "mcp = FastMCP(" in line_content and ")" in line_content and not otel_args_injected:
                open_paren_pos = line_content.find("(")
                close_paren_pos = line_content.rfind(")")
                if open_paren_pos != -1 and close_paren_pos != -1 and open_paren_pos < close_paren_pos:
                    existing_args_str = line_content[open_paren_pos+1:close_paren_pos].strip()
                    otel_args_to_add = []
                    if "lifespan=" not in existing_args_str:
                        otel_args_to_add.append("lifespan=otel_lifespan")
                    if settings.transport != "stdio" and "middleware=" not in existing_args_str:
                        otel_args_to_add.append("middleware=[Middleware(OpenTelemetryMiddleware)]")
                    
                    if otel_args_to_add:
                        new_args_str = existing_args_str
                        if new_args_str and not new_args_str.endswith(','):
                            new_args_str += ", "
                        new_args_str += ", ".join(otel_args_to_add)
                        new_line = f"{line_content[:open_paren_pos+1]}{new_args_str}{line_content[close_paren_pos:]}"
                        final_mcp_lines.append(new_line)
                        otel_args_injected = True
                        continue
            final_mcp_lines.append(line_content)
        
        if otel_args_injected:
            auth_code_str = "\n".join(final_mcp_lines)
        elif otel_args_to_add: # Only warn if we actually tried to add something
            console.print(f"[yellow]Warning: Could not automatically inject OpenTelemetry lifespan/middleware into FastMCP constructor. Review server.py.[/yellow]")
    # ---- END Centralized OpenTelemetry Argument Injection ----

    # ---- MODIFICATION TO auth_code_str for _set_active_golf_oauth_provider (if auth was enabled) ----
    if provider_config: # Only run this if auth was actually processed by generate_auth_code
        auth_routes_code = generate_auth_routes()

        server_file = output_dir / "server.py"
        if server_file.exists():
            with open(server_file, "r") as f:
                server_code_content = f.read()
            
            create_marker = '# Create FastMCP server'
            # The original logic replaces the FastMCP instantiation part.
            # So we use the modified auth_code_str here.
            create_pos = server_code_content.find(create_marker)
            if create_pos != -1: # Ensure marker is found
                create_pos += len(create_marker) # Move past the marker text itself
                create_next_line = server_code_content.find('\n', create_pos) + 1
                # Assuming the original mcp = FastMCP(...) line is what auth_code_str replaces
                # Find the end of the line that starts with "mcp = FastMCP("
                mcp_line_start_search = server_code_content.find("mcp = FastMCP(", create_next_line)
                if mcp_line_start_search != -1:
                    mcp_line_end = server_code_content.find('\n', mcp_line_start_search)
                    if mcp_line_end == -1: mcp_line_end = len(server_code_content) # if it's the last line

                    modified_code = (
                        server_code_content[:create_next_line] + 
                        auth_code_str + # Use the modified auth code string
                        server_code_content[mcp_line_end:]
                    )
                else: # Fallback if "mcp = FastMCP(" line isn't found as expected
                    console.print(f"[yellow]Warning: Could not precisely find 'mcp = FastMCP(...)' line for replacement by auth_code in {server_file}. Appending auth_code instead.[/yellow]")
                    # This part of the logic was to replace mcp = FastMCP(...)
                    # If the generate_auth_code ALREADY includes the mcp = FastMCP(...) line,
                    # then the original injection logic might be different.
                    # The example server.py shows that the auth_code INCLUDES the mcp = FastMCP(...) line.
                    # The original code in builder.py:
                    # create_next_line = server_code.find('\n', create_pos) + 1
                    # mcp_line_end = server_code.find('\n', create_next_line)
                    # This implies it replaces ONE line after '# Create FastMCP server'
                    # This needs to be robust. If auth_code_str contains the `mcp = FastMCP(...)` line itself,
                    # then this replacement logic is correct.
                    
                    # The server.py example from `new/dist` implies that auth_code effectively *is* the
                    # whole block from "import os" for auth settings down to and including "mcp = FastMCP(...)".
                    # The original `_generate_server` creates a very minimal `mcp = FastMCP(...)`.
                    # The `build_project` then overwrites this with the richer `auth_code` block.
                    # Let's assume `auth_code_str_modified` should replace from `create_next_line` up to
                    # where the original `mcp = FastMCP(...)` definition ended.

                    # Re-evaluating the injection for auth_code_str_modified.
                    # The server.py is first generated by _generate_server.
                    # Then, if auth is enabled, this part of build_project MODIFIES it.
                    # It finds '# Create FastMCP server', then replaces the *next line* (which is `mcp = FastMCP(...)` from _generate_server)
                    # with the entire `auth_code_str_modified`.
                    
                    # Original line to find/replace: `mcp = FastMCP("{self.settings.name}")`
                    # OR if telemetry was on `mcp = FastMCP("{self.settings.name}", lifespan=otel_lifespan)`
                    # The replacement logic must be robust to find the line created by _generate_server
                    
                    # Let's find the line starting with "mcp = FastMCP(" that _generate_server created
                    original_mcp_instantiation_pattern = "mcp = FastMCP("
                    start_replace_idx = server_code_content.find(original_mcp_instantiation_pattern)
                    
                    if start_replace_idx != -1:
                        # We need to find the complete statement, including any continuation lines
                        line_start = server_code_content.rfind('\n', 0, start_replace_idx) + 1
                        
                        # Find the closing parenthesis, handling potential multi-line calls
                        opening_paren_pos = server_code_content.find('(', start_replace_idx)
                        if opening_paren_pos != -1:
                            # Count open parentheses to handle nested ones correctly
                            paren_count = 1
                            pos = opening_paren_pos + 1
                            while pos < len(server_code_content) and paren_count > 0:
                                if server_code_content[pos] == '(':
                                    paren_count += 1
                                elif server_code_content[pos] == ')':
                                    paren_count -= 1
                                pos += 1
                            
                            closing_paren_pos = pos - 1 if paren_count == 0 else -1
                            
                            if closing_paren_pos != -1:
                                # Find the end of the statement (newline after the closing parenthesis)
                                next_newline = server_code_content.find('\n', closing_paren_pos)
                                if next_newline != -1:
                                    end_replace_idx = next_newline + 1
                                else:
                                    end_replace_idx = len(server_code_content)
                                
                                # Replace the entire statement with the auth code
                                modified_code = (
                                    server_code_content[:line_start] +
                                    auth_code_str + 
                                    server_code_content[end_replace_idx:]
                                )
                            else:
                                console.print(f"[red]Error: Could not find closing parenthesis for FastMCP constructor in {server_file}. Auth injection may fail.[/red]")
                                modified_code = server_code_content
                        else:
                            console.print(f"[red]Error: Could not find opening parenthesis for FastMCP constructor in {server_file}. Auth injection may fail.[/red]")
                            modified_code = server_code_content
            
            else: # create_marker not found (This case should ideally not happen if _generate_server works)
                console.print(f"[red]Could not find injection marker '{create_marker}' in {server_file}. Auth injection failed.[/red]")
                modified_code = server_code_content # No change

            app_marker = 'if __name__ == "__main__":'
            app_pos = modified_code.find(app_marker)
            if app_pos != -1: # Ensure marker is found
                modified_code = (
                    modified_code[:app_pos] + 
                    auth_routes_code + "\n\n" + # Ensure auth routes are injected
                    modified_code[app_pos:]
                )
            else:
                console.print(f"[yellow]Warning: Could not find main block marker '{app_marker}' in {server_file} to inject auth routes.[/yellow]")

            # Format with black before writing
            try:
                final_code_to_write = black.format_str(modified_code, mode=black.Mode())
            except Exception as e:
                console.print(f"[yellow]Warning: Could not format server.py after auth injection: {e}[/yellow]")
                final_code_to_write = modified_code # Write unformatted if black fails

            with open(server_file, "w") as f:
                f.write(final_code_to_write)
            
        else: # server_file does not exist
            console.print(f"[red]Error: {server_file} does not exist for auth modification. Ensure _generate_server runs first.[/red]")


# Renamed function - was find_shared_modules
def find_common_files(project_path: Path, components: Dict[ComponentType, List[ParsedComponent]]) -> Dict[str, Path]:
    """Find all common.py files used by components."""
    # We'll use the parser's functionality to find common files directly
    from golf.core.parser import parse_common_files
    common_files = parse_common_files(project_path)
    
    # Return the found files without debug messages
    return common_files


# Updated parameter name from shared_modules to common_files
def build_import_map(project_path: Path, common_files: Dict[str, Path]) -> Dict[str, str]:
    """Build a mapping of import paths to their new locations in the build output.
    
    This maps from original relative import paths to absolute import paths
    in the components directory structure.
    """
    import_map = {}
    
    for dir_path_str, file_path in common_files.items():
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
            new_path = f"components.{component_type}.{rel_to_component}".replace("/", ".")
            # Fix any double dots
            new_path = new_path.replace("..", ".")
            
            # Map both the directory and the common file
            orig_module = dir_path_str
            import_map[orig_module] = new_path
            
            # Also map the specific common module
            common_module = f"{dir_path_str}/common"
            import_map[common_module] = f"{new_path}.common"
        except ValueError:
            continue
    
    return import_map