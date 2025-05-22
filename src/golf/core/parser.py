"""Python file parser for extracting tools, resources, and prompts using AST."""

import ast
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

console = Console()


class ComponentType(str, Enum):
    """Type of component discovered by the parser."""
    
    TOOL = "tool"
    RESOURCE = "resource"
    PROMPT = "prompt"
    UNKNOWN = "unknown"


@dataclass
class ParsedComponent:
    """Represents a parsed MCP component (tool, resource, or prompt)."""
    
    name: str  # Derived from file path or explicit name
    type: ComponentType
    file_path: Path
    module_path: str
    docstring: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    uri_template: Optional[str] = None  # For resources
    parameters: Optional[List[str]] = None  # For resources with URI params
    parent_module: Optional[str] = None  # For nested components
    entry_function: Optional[str] = None  # Store the name of the function to use


class AstParser:
    """AST-based parser for extracting MCP components from Python files."""
    
    def __init__(self, project_root: Path):
        """Initialize the parser.
        
        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root
        self.components: Dict[str, ParsedComponent] = {}
    
    def parse_directory(self, directory: Path) -> List[ParsedComponent]:
        """Parse all Python files in a directory recursively."""
        components = []
        
        for file_path in directory.glob("**/*.py"):
            # Skip __pycache__ and other hidden directories
            if "__pycache__" in file_path.parts or any(part.startswith('.') for part in file_path.parts):
                continue
            
            try:
                file_components = self.parse_file(file_path)
                components.extend(file_components)
            except Exception as e:
                relative_path = file_path.relative_to(self.project_root)
                console.print(f"[bold red]Error parsing {relative_path}:[/bold red] {e}")
        
        return components
    
    def parse_file(self, file_path: Path) -> List[ParsedComponent]:
        """Parse a single Python file using AST to extract MCP components."""
        # Handle common.py files
        if file_path.name == "common.py":
            # Register as a known shared module but don't return as a component
            return []
            
        # Skip __init__.py files for direct parsing
        if file_path.name == "__init__.py":
            return []
            
        # Determine component type based on directory structure
        rel_path = file_path.relative_to(self.project_root)
        parent_dir = rel_path.parts[0] if rel_path.parts else None
        
        component_type = ComponentType.UNKNOWN
        if parent_dir == "tools":
            component_type = ComponentType.TOOL
        elif parent_dir == "resources":
            component_type = ComponentType.RESOURCE
        elif parent_dir == "prompts":
            component_type = ComponentType.PROMPT
        
        if component_type == ComponentType.UNKNOWN:
            return []  # Not in a recognized directory
        
        # Read the file content and parse it with AST
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        try:
            tree = ast.parse(file_content)
        except SyntaxError as e:
            raise ValueError(f"Syntax error in {file_path}: {e}")
        
        # Extract module docstring
        module_docstring = ast.get_docstring(tree)
        if not module_docstring:
            raise ValueError(f"Missing module docstring in {file_path}")
        
        # Find the entry function - look for "export = function_name" pattern, 
        # or any top-level function (like "run") as a fallback
        entry_function = None
        export_target = None
        
        # Look for export = function_name assignment
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "export":
                        if isinstance(node.value, ast.Name):
                            export_target = node.value.id
                            break
        
        # Find all top-level functions
        functions = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node)
                # If this function matches our export target, it's our entry function
                if export_target and node.name == export_target:
                    entry_function = node
        
        # Check for the run function as a fallback
        run_function = None
        for func in functions:
            if func.name == "run":
                run_function = func
                
        # If we have an export but didn't find the target function, warn
        if export_target and not entry_function:
            console.print(f"[yellow]Warning: Export target '{export_target}' not found in {file_path}[/yellow]")
        
        # Use the export target function if found, otherwise fall back to run
        entry_function = entry_function or run_function
        
        # If no valid function found, skip this file
        if not entry_function:
            return []
        
        # Create component
        component = ParsedComponent(
            name="",  # Will be set later
            type=component_type,
            file_path=file_path,
            module_path=file_path.relative_to(self.project_root).as_posix(),
            docstring=module_docstring,
            entry_function=export_target or "run"  # Store the name of the entry function
        )
        
        # Process the entry function
        self._process_entry_function(component, entry_function, tree, file_path)
        
        # Process other component-specific information
        if component_type == ComponentType.TOOL:
            self._process_tool(component, tree)
        elif component_type == ComponentType.RESOURCE:
            self._process_resource(component, tree)
        elif component_type == ComponentType.PROMPT:
            self._process_prompt(component, tree)
        
        # Set component name based on file path
        component.name = self._derive_component_name(file_path, component_type)
        
        # Set parent module if it's in a nested structure
        if len(rel_path.parts) > 2:  # More than just "tools/file.py"
            parent_parts = rel_path.parts[1:-1]  # Skip the root category and the file itself
            if parent_parts:
                component.parent_module = ".".join(parent_parts)
        
        return [component]
    
    def _process_entry_function(self, component: ParsedComponent, func_node: ast.FunctionDef | ast.AsyncFunctionDef, tree: ast.Module, file_path: Path) -> None:
        """Process the entry function to extract parameters and return type."""
        # Extract function docstring
        func_docstring = ast.get_docstring(func_node)
        
        # Extract parameter names and annotations
        parameters = []
        for arg in func_node.args.args:
            # Skip self, cls parameters
            if arg.arg in ("self", "cls"):
                continue
                
            # Skip ctx parameter - GolfMCP will inject this
            if arg.arg == "ctx":
                continue
                
            parameters.append(arg.arg)
        
        # Check for return annotation - STRICT requirement
        if func_node.returns is None:
            raise ValueError(f"Missing return annotation for {func_node.name} function in {file_path}")
        
        # Store parameters
        component.parameters = parameters
    
    def _process_tool(self, component: ParsedComponent, tree: ast.Module) -> None:
        """Process a tool component to extract input/output schemas."""
        # Look for Input and Output classes in the AST
        input_class = None
        output_class = None
        
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                if node.name == "Input":
                    input_class = node
                elif node.name == "Output":
                    output_class = node
        
        # Process Input class if found
        if input_class:
            # Check if it inherits from BaseModel
            for base in input_class.bases:
                if isinstance(base, ast.Name) and base.id == "BaseModel":
                    component.input_schema = self._extract_pydantic_schema_from_ast(input_class)
                    break
        
        # Process Output class if found
        if output_class:
            # Check if it inherits from BaseModel
            for base in output_class.bases:
                if isinstance(base, ast.Name) and base.id == "BaseModel":
                    component.output_schema = self._extract_pydantic_schema_from_ast(output_class)
                    break
    
    def _process_resource(self, component: ParsedComponent, tree: ast.Module) -> None:
        """Process a resource component to extract URI template."""
        # Look for resource_uri assignment in the AST
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "resource_uri":
                        if isinstance(node.value, ast.Constant):
                            uri_template = node.value.value
                            component.uri_template = uri_template
                            
                            # Extract URI parameters (parts in {})
                            uri_params = re.findall(r"{([^}]+)}", uri_template)
                            if uri_params:
                                component.parameters = uri_params
                            break
    
    def _process_prompt(self, component: ParsedComponent, tree: ast.Module) -> None:
        """Process a prompt component (no special processing needed)."""
        pass
    
    def _derive_component_name(self, file_path: Path, component_type: ComponentType) -> str:
        """Derive a component name from its file path according to the spec.
        
        Following the spec: <filename> + ("-" + "-".join(PathRev) if PathRev else "")
        where PathRev is the reversed list of parent directories under the category.
        """
        rel_path = file_path.relative_to(self.project_root)
        
        # Find which category directory this is in
        category = None
        category_idx = -1
        for i, part in enumerate(rel_path.parts):
            if part in ["tools", "resources", "prompts"]:
                category = part
                category_idx = i
                break
        
        if category_idx == -1:
            return ""
        
        # Get the filename without extension
        filename = rel_path.stem
        
        # Get parent directories between category and file
        parent_dirs = list(rel_path.parts[category_idx+1:-1])
        
        # Reverse parent dirs according to spec
        parent_dirs.reverse()
        
        # Form the ID according to spec
        if parent_dirs:
            return f"{filename}-{'-'.join(parent_dirs)}"
        else:
            return filename
    
    def _extract_pydantic_schema_from_ast(self, class_node: ast.ClassDef) -> Dict[str, Any]:
        """Extract a JSON schema from an AST class definition.
        
        This is a simplified version that extracts basic field information.
        For complex annotations, a more sophisticated approach would be needed.
        """
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for node in class_node.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                field_name = node.target.id
                
                # Extract type annotation as string
                annotation = ""
                if isinstance(node.annotation, ast.Name):
                    annotation = node.annotation.id
                elif isinstance(node.annotation, ast.Subscript):
                    # Simple handling of things like List[str]
                    annotation = ast.unparse(node.annotation)
                else:
                    annotation = ast.unparse(node.annotation)
                
                # Create property definition
                prop = {
                    "type": self._type_hint_to_json_type(annotation),
                    "title": field_name.replace('_', ' ').title()
                }
                
                # Extract default value if present
                if node.value is not None:
                    if isinstance(node.value, ast.Constant):
                        # Simple constant default
                        prop["default"] = node.value.value
                    elif (isinstance(node.value, ast.Call) and 
                          isinstance(node.value.func, ast.Name) and 
                          node.value.func.id == "Field"):
                        # Field object - extract its parameters
                        for keyword in node.value.keywords:
                            if keyword.arg == "default" or keyword.arg == "default_factory":
                                if isinstance(keyword.value, ast.Constant):
                                    prop["default"] = keyword.value.value
                            elif keyword.arg == "description":
                                if isinstance(keyword.value, ast.Constant):
                                    prop["description"] = keyword.value.value
                            elif keyword.arg == "title":
                                if isinstance(keyword.value, ast.Constant):
                                    prop["title"] = keyword.value.value
                        
                        # Check for position default argument (Field(..., "description"))
                        if node.value.args:
                            for i, arg in enumerate(node.value.args):
                                if i == 0 and isinstance(arg, ast.Constant) and arg.value != Ellipsis:
                                    prop["default"] = arg.value
                                elif i == 1 and isinstance(arg, ast.Constant):
                                    prop["description"] = arg.value
                
                # Add to properties
                schema["properties"][field_name] = prop
                
                # Check if required (no default value or Field(...))
                is_required = True
                if node.value is not None:
                    if isinstance(node.value, ast.Constant):
                        is_required = False
                    elif (isinstance(node.value, ast.Call) and 
                          isinstance(node.value.func, ast.Name) and 
                          node.value.func.id == "Field"):
                        # Field has default if it doesn't use ... or if it has a default keyword
                        has_ellipsis = False
                        has_default = False
                        
                        if node.value.args and isinstance(node.value.args[0], ast.Constant):
                            has_ellipsis = node.value.args[0].value is Ellipsis
                        
                        for keyword in node.value.keywords:
                            if keyword.arg == "default" or keyword.arg == "default_factory":
                                has_default = True
                        
                        is_required = has_ellipsis and not has_default
                
                if is_required:
                    schema["required"].append(field_name)
        
        return schema
    
    def _type_hint_to_json_type(self, type_hint: str) -> str:
        """Convert a Python type hint to a JSON schema type.
        
        This is a simplified version. A more sophisticated approach would
        handle complex types correctly.
        """
        type_map = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
        }
        
        # Handle simple types
        for py_type, json_type in type_map.items():
            if py_type in type_hint.lower():
                return json_type
        
        # Default to string for unknown types
        return "string"


def parse_project(project_path: Path) -> Dict[ComponentType, List[ParsedComponent]]:
    """Parse a GolfMCP project to extract all components."""
    parser = AstParser(project_path)
    
    components: Dict[ComponentType, List[ParsedComponent]] = {
        ComponentType.TOOL: [],
        ComponentType.RESOURCE: [],
        ComponentType.PROMPT: []
    }
    
    # Parse each directory
    for comp_type, dir_name in [
        (ComponentType.TOOL, "tools"),
        (ComponentType.RESOURCE, "resources"),
        (ComponentType.PROMPT, "prompts")
    ]:
        dir_path = project_path / dir_name
        if dir_path.exists() and dir_path.is_dir():
            dir_components = parser.parse_directory(dir_path)
            components[comp_type].extend([c for c in dir_components if c.type == comp_type])
    
    # Check for ID collisions
    all_ids = []
    for comp_type, comps in components.items():
        for comp in comps:
            if comp.name in all_ids:
                raise ValueError(f"ID collision detected: {comp.name} is used by multiple components")
            all_ids.append(comp.name)
    
    return components





def parse_common_files(project_path: Path) -> Dict[str, Path]:
    """Find all common.py files in the project.
    
    Args:
        project_path: Path to the project root
        
    Returns:
        Dictionary mapping directory paths to common.py file paths
    """
    common_files = {}
    
    # Search for common.py files in tools, resources, and prompts directories
    for dir_name in ["tools", "resources", "prompts"]:
        base_dir = project_path / dir_name
        if not base_dir.exists() or not base_dir.is_dir():
            continue
            
        # Find all common.py files (recursively)
        for common_file in base_dir.glob("**/common.py"):
            # Skip files in __pycache__ or other hidden directories
            if "__pycache__" in common_file.parts or any(part.startswith('.') for part in common_file.parts):
                continue
                
            # Get the parent directory as the module path
            module_path = str(common_file.parent.relative_to(project_path))
            common_files[module_path] = common_file
    
    return common_files 