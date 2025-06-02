"""Python file parser for extracting tools, resources, and prompts using AST."""

import ast
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


class ComponentType(str, Enum):
    """Type of component discovered by the parser."""

    TOOL = "tool"
    RESOURCE = "resource"
    PROMPT = "prompt"
    ROUTE = "route"
    UNKNOWN = "unknown"


@dataclass
class ParsedComponent:
    """Represents a parsed MCP component (tool, resource, or prompt)."""

    name: str  # Derived from file path or explicit name
    type: ComponentType
    file_path: Path
    module_path: str
    docstring: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    uri_template: str | None = None  # For resources
    parameters: list[str] | None = None  # For resources with URI params
    parent_module: str | None = None  # For nested components
    entry_function: str | None = None  # Store the name of the function to use
    annotations: dict[str, Any] | None = None  # Tool annotations for MCP hints


class AstParser:
    """AST-based parser for extracting MCP components from Python files."""

    def __init__(self, project_root: Path) -> None:
        """Initialize the parser.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root
        self.components: dict[str, ParsedComponent] = {}

    def parse_directory(self, directory: Path) -> list[ParsedComponent]:
        """Parse all Python files in a directory recursively."""
        components = []

        for file_path in directory.glob("**/*.py"):
            # Skip __pycache__ and other hidden directories
            if "__pycache__" in file_path.parts or any(
                part.startswith(".") for part in file_path.parts
            ):
                continue

            try:
                file_components = self.parse_file(file_path)
                components.extend(file_components)
            except Exception as e:
                relative_path = file_path.relative_to(self.project_root)
                console.print(
                    f"[bold red]Error parsing {relative_path}:[/bold red] {e}"
                )

        return components

    def parse_file(self, file_path: Path) -> list[ParsedComponent]:
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
        with open(file_path, encoding="utf-8") as f:
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
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
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
            console.print(
                f"[yellow]Warning: Export target '{export_target}' not found in {file_path}[/yellow]"
            )

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
            entry_function=export_target
            or "run",  # Store the name of the entry function
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
            parent_parts = rel_path.parts[
                1:-1
            ]  # Skip the root category and the file itself
            if parent_parts:
                component.parent_module = ".".join(parent_parts)

        return [component]

    def _process_entry_function(
        self,
        component: ParsedComponent,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        tree: ast.Module,
        file_path: Path,
    ) -> None:
        """Process the entry function to extract parameters and return type."""
        # Extract function docstring
        ast.get_docstring(func_node)

        # Extract parameter names and build input schema
        parameters = []
        input_properties = {}
        required_params = []

        for i, arg in enumerate(func_node.args.args):
            # Skip self, cls parameters
            if arg.arg in ("self", "cls"):
                continue

            # Skip ctx parameter - GolfMCP will inject this
            if arg.arg == "ctx":
                continue

            parameters.append(arg.arg)

            # Extract type annotation and Field metadata if present
            if arg.annotation:
                prop_schema = self._extract_parameter_schema(arg, func_node.args.defaults, len(func_node.args.args))
                if prop_schema:
                    input_properties[arg.arg] = prop_schema
                    # Check if parameter is required (no default value)
                    if self._is_parameter_required(i, func_node.args.defaults, len(func_node.args.args)):
                        required_params.append(arg.arg)

        # Build input schema if we have parameters
        if input_properties:
            component.input_schema = {
                "type": "object",
                "properties": input_properties,
                "required": required_params
            }

        # Extract output schema from return type annotation
        if func_node.returns:
            output_schema = self._extract_return_type_schema(func_node.returns, tree)
            if output_schema:
                component.output_schema = output_schema

        # Check for return annotation - STRICT requirement
        if func_node.returns is None:
            raise ValueError(
                f"Missing return annotation for {func_node.name} function in {file_path}"
            )

        # Store parameters
        component.parameters = parameters

    def _process_tool(self, component: ParsedComponent, tree: ast.Module) -> None:
        """Process a tool component to extract input/output schemas and annotations."""
        # Look for Input and Output classes in the AST
        input_class = None
        output_class = None
        annotations = None

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                if node.name == "Input":
                    input_class = node
                elif node.name == "Output":
                    output_class = node
            # Look for annotations assignment
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "annotations":
                        if isinstance(node.value, ast.Dict):
                            annotations = self._extract_dict_from_ast(node.value)
                        break

        # Process Input class if found
        if input_class:
            # Check if it inherits from BaseModel
            for base in input_class.bases:
                if isinstance(base, ast.Name) and base.id == "BaseModel":
                    component.input_schema = self._extract_pydantic_schema_from_ast(
                        input_class
                    )
                    break

        # Process Output class if found
        if output_class:
            # Check if it inherits from BaseModel
            for base in output_class.bases:
                if isinstance(base, ast.Name) and base.id == "BaseModel":
                    component.output_schema = self._extract_pydantic_schema_from_ast(
                        output_class
                    )
                    break

        # Store annotations if found
        if annotations:
            component.annotations = annotations

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

    def _derive_component_name(
        self, file_path: Path, component_type: ComponentType
    ) -> str:
        """Derive a component name from its file path according to the spec.

        Following the spec: <filename> + ("-" + "-".join(PathRev) if PathRev else "")
        where PathRev is the reversed list of parent directories under the category.
        """
        rel_path = file_path.relative_to(self.project_root)

        # Find which category directory this is in
        category_idx = -1
        for i, part in enumerate(rel_path.parts):
            if part in ["tools", "resources", "prompts"]:
                category_idx = i
                break

        if category_idx == -1:
            return ""

        # Get the filename without extension
        filename = rel_path.stem

        # Get parent directories between category and file
        parent_dirs = list(rel_path.parts[category_idx + 1 : -1])

        # Reverse parent dirs according to spec
        parent_dirs.reverse()

        # Form the ID according to spec
        if parent_dirs:
            return f"{filename}-{'-'.join(parent_dirs)}"
        else:
            return filename

    def _extract_pydantic_schema_from_ast(
        self, class_node: ast.ClassDef
    ) -> dict[str, Any]:
        """Extract a JSON schema from an AST class definition.

        This is a simplified version that extracts basic field information.
        For complex annotations, a more sophisticated approach would be needed.
        """
        schema = {"type": "object", "properties": {}, "required": []}

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
                    "title": field_name.replace("_", " ").title(),
                }

                # Extract default value if present
                if node.value is not None:
                    if isinstance(node.value, ast.Constant):
                        # Simple constant default
                        prop["default"] = node.value.value
                    elif (
                        isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == "Field"
                    ):
                        # Field object - extract its parameters
                        for keyword in node.value.keywords:
                            if (
                                keyword.arg == "default"
                                or keyword.arg == "default_factory"
                            ):
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
                                if (
                                    i == 0
                                    and isinstance(arg, ast.Constant)
                                    and arg.value != Ellipsis
                                ):
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
                    elif (
                        isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == "Field"
                    ):
                        # Field has default if it doesn't use ... or if it has a default keyword
                        has_ellipsis = False
                        has_default = False

                        if node.value.args and isinstance(
                            node.value.args[0], ast.Constant
                        ):
                            has_ellipsis = node.value.args[0].value is Ellipsis

                        for keyword in node.value.keywords:
                            if (
                                keyword.arg == "default"
                                or keyword.arg == "default_factory"
                            ):
                                has_default = True

                        is_required = has_ellipsis and not has_default

                if is_required:
                    schema["required"].append(field_name)

        return schema

    def _type_hint_to_json_type(self, type_hint: str) -> str:
        """Convert a Python type hint to a JSON schema type.

        This handles complex types and edge cases better than the original version.
        """
        # Handle None type
        if type_hint.lower() in ["none", "nonetype"]:
            return "null"
        
        # Handle basic types first
        type_map = {
            "str": "string",
            "int": "integer", 
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
            "any": "object"  # Any maps to object
        }

        # Exact matches for simple types
        lower_hint = type_hint.lower()
        if lower_hint in type_map:
            return type_map[lower_hint]

        # Handle common complex patterns
        if "list[" in type_hint or "List[" in type_hint:
            return "array"
        elif "dict[" in type_hint or "Dict[" in type_hint:
            return "object"
        elif "union[" in type_hint or "Union[" in type_hint:
            # For Union types, try to extract the first non-None type
            if "none" in lower_hint or "nonetype" in lower_hint:
                # This is Optional[SomeType] - extract the SomeType
                for basic_type in type_map:
                    if basic_type in lower_hint:
                        return type_map[basic_type]
            return "object"  # Fallback for complex unions
        elif "optional[" in type_hint or "Optional[" in type_hint:
            # Extract the wrapped type from Optional[Type]
            for basic_type in type_map:
                if basic_type in lower_hint:
                    return type_map[basic_type]
            return "object"

        # Handle some common pydantic/typing types
        if any(keyword in lower_hint for keyword in ["basemodel", "model"]):
            return "object"
        
        # Check for numeric patterns
        if any(num_type in lower_hint for num_type in ["int", "integer", "number"]):
            return "integer"
        elif any(num_type in lower_hint for num_type in ["float", "double", "decimal"]):
            return "number"
        elif any(str_type in lower_hint for str_type in ["str", "string", "text"]):
            return "string"
        elif any(bool_type in lower_hint for bool_type in ["bool", "boolean"]):
            return "boolean"

        # Default to object for unknown complex types, string for simple unknowns
        if "[" in type_hint or "." in type_hint:
            return "object"
        else:
            return "string"

    def _extract_dict_from_ast(self, dict_node: ast.Dict) -> dict[str, Any]:
        """Extract a dictionary from an AST Dict node.

        This handles simple literal dictionaries with string keys and
        boolean/string/number values.
        """
        result = {}

        for key, value in zip(dict_node.keys, dict_node.values, strict=False):
            # Extract the key
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                key_str = key.value
            elif isinstance(key, ast.Str):  # For older Python versions
                key_str = key.s
            else:
                # Skip non-string keys
                continue

            # Extract the value
            if isinstance(value, ast.Constant):
                # Handles strings, numbers, booleans, None
                result[key_str] = value.value
            elif isinstance(value, ast.Str):  # For older Python versions
                result[key_str] = value.s
            elif isinstance(value, ast.Num):  # For older Python versions
                result[key_str] = value.n
            elif isinstance(
                value, ast.NameConstant
            ):  # For older Python versions (True/False/None)
                result[key_str] = value.value
            elif isinstance(value, ast.Name):
                # Handle True/False/None as names
                if value.id in ("True", "False", "None"):
                    result[key_str] = {"True": True, "False": False, "None": None}[
                        value.id
                    ]
            # We could add more complex value handling here if needed

        return result

    def _extract_parameter_schema(self, arg: ast.arg, defaults: list, total_args: int) -> dict[str, Any] | None:
        """Extract JSON schema from a function parameter annotation."""
        if not arg.annotation:
            return None

        # Handle Annotated types like Annotated[str, Field(description="...")]
        if isinstance(arg.annotation, ast.Subscript):
            annotation_str = ast.unparse(arg.annotation)
            
            # Check if this is an Annotated type
            if annotation_str.startswith("Annotated["):
                # Extract the base type and Field metadata
                return self._extract_annotated_schema(arg.annotation)
            else:
                # Handle other subscripted types like list[str], dict[str, Any], etc.
                return self._extract_complex_type_schema(arg.annotation)
        
        # Handle simple types like str, int, bool
        elif isinstance(arg.annotation, ast.Name):
            base_type = self._type_hint_to_json_type(arg.annotation.id)
            return {
                "type": base_type,
                "title": arg.arg.replace("_", " ").title()
            }
        
        # Handle union types and other complex annotations
        else:
            annotation_str = ast.unparse(arg.annotation)
            base_type = self._type_hint_to_json_type(annotation_str)
            return {
                "type": base_type,
                "title": arg.arg.replace("_", " ").title()
            }

    def _extract_annotated_schema(self, annotation: ast.Subscript) -> dict[str, Any] | None:
        """Extract schema from Annotated[Type, Field(...)] annotation."""
        if not isinstance(annotation.value, ast.Name) or annotation.value.id != "Annotated":
            return None
        
        if not hasattr(annotation, 'slice') or not isinstance(annotation.slice, ast.Tuple):
            return None
        
        if len(annotation.slice.elts) < 2:
            return None
        
        # First element is the base type
        base_type_node = annotation.slice.elts[0]
        base_type = self._extract_type_from_node(base_type_node)
        
        # Initialize schema with base type
        schema = {
            "type": base_type["type"] if isinstance(base_type, dict) else base_type,
            "title": ""
        }
        
        # Merge any additional type info
        if isinstance(base_type, dict):
            schema.update(base_type)
        
        # Second element is usually Field(...)
        field_node = annotation.slice.elts[1]
        if isinstance(field_node, ast.Call) and isinstance(field_node.func, ast.Name) and field_node.func.id == "Field":
            # Extract Field parameters
            field_info = self._extract_field_info(field_node)
            schema.update(field_info)
        
        return schema

    def _extract_field_info(self, field_call: ast.Call) -> dict[str, Any]:
        """Extract information from a Field(...) call."""
        info = {}
        
        # Process keyword arguments
        for keyword in field_call.keywords:
            if keyword.arg == "description":
                if isinstance(keyword.value, ast.Constant):
                    info["description"] = keyword.value.value
            elif keyword.arg == "title":
                if isinstance(keyword.value, ast.Constant):
                    info["title"] = keyword.value.value
            elif keyword.arg == "default":
                if isinstance(keyword.value, ast.Constant):
                    info["default"] = keyword.value.value
            elif keyword.arg == "ge":
                if isinstance(keyword.value, ast.Constant):
                    info["minimum"] = keyword.value.value
            elif keyword.arg == "le":
                if isinstance(keyword.value, ast.Constant):
                    info["maximum"] = keyword.value.value
            elif keyword.arg == "gt":
                if isinstance(keyword.value, ast.Constant):
                    info["exclusiveMinimum"] = keyword.value.value
            elif keyword.arg == "lt":
                if isinstance(keyword.value, ast.Constant):
                    info["exclusiveMaximum"] = keyword.value.value
        
        # Process positional arguments (first one is usually default, second is description)
        for i, arg in enumerate(field_call.args):
            if i == 0 and isinstance(arg, ast.Constant) and arg.value != Ellipsis:
                info["default"] = arg.value
            elif i == 1 and isinstance(arg, ast.Constant):
                info["description"] = arg.value
        
        return info

    def _extract_type_from_node(self, type_node: ast.AST) -> dict[str, Any] | str:
        """Extract type information from an AST node."""
        if isinstance(type_node, ast.Name):
            return self._type_hint_to_json_type(type_node.id)
        elif isinstance(type_node, ast.Subscript):
            return self._extract_complex_type_schema(type_node)
        elif isinstance(type_node, ast.BinOp) and isinstance(type_node.op, ast.BitOr):
            # Handle union types like str | None
            return self._handle_union_type(type_node)
        else:
            # Fallback to string representation
            type_str = ast.unparse(type_node)
            return self._type_hint_to_json_type(type_str)

    def _extract_complex_type_schema(self, subscript: ast.Subscript) -> dict[str, Any]:
        """Extract schema from complex types like list[str], dict[str, Any], etc."""
        if isinstance(subscript.value, ast.Name):
            base_type = subscript.value.id
            
            if base_type == "list":
                # Handle list[ItemType]
                if isinstance(subscript.slice, ast.Name):
                    item_type = self._type_hint_to_json_type(subscript.slice.id)
                elif isinstance(subscript.slice, ast.Subscript):
                    item_schema = self._extract_complex_type_schema(subscript.slice)
                    return {
                        "type": "array",
                        "items": item_schema
                    }
                else:
                    # Complex item type, try to parse it
                    item_type_str = ast.unparse(subscript.slice)
                    if "dict" in item_type_str.lower():
                        return {
                            "type": "array",
                            "items": {"type": "object"}
                        }
                    else:
                        item_type = self._type_hint_to_json_type(item_type_str)
                
                return {
                    "type": "array",
                    "items": {"type": item_type}
                }
            
            elif base_type == "dict":
                return {"type": "object"}
            
            elif base_type in ["Optional", "Union"]:
                # Handle Optional[Type] or Union[Type, None]
                return self._handle_optional_type(subscript)
        
        # Fallback
        type_str = ast.unparse(subscript)
        return {"type": self._type_hint_to_json_type(type_str)}

    def _handle_union_type(self, union_node: ast.BinOp) -> dict[str, Any]:
        """Handle union types like str | None."""
        # For now, just extract the first non-None type
        left_type = self._extract_type_from_node(union_node.left)
        right_type = self._extract_type_from_node(union_node.right)
        
        # If one side is None, return the other type
        if isinstance(right_type, str) and right_type == "null":
            return left_type if isinstance(left_type, dict) else {"type": left_type}
        elif isinstance(left_type, str) and left_type == "null":
            return right_type if isinstance(right_type, dict) else {"type": right_type}
        
        # Otherwise, return the first type
        return left_type if isinstance(left_type, dict) else {"type": left_type}

    def _handle_optional_type(self, subscript: ast.Subscript) -> dict[str, Any]:
        """Handle Optional[Type] annotations."""
        if isinstance(subscript.slice, ast.Name):
            base_type = self._type_hint_to_json_type(subscript.slice.id)
            return {"type": base_type}
        elif isinstance(subscript.slice, ast.Subscript):
            return self._extract_complex_type_schema(subscript.slice)
        else:
            type_str = ast.unparse(subscript.slice)
            return {"type": self._type_hint_to_json_type(type_str)}

    def _is_parameter_required(self, position: int, defaults: list, total_args: int) -> bool:
        """Check if a function parameter is required (has no default value)."""
        if position >= total_args or position < 0:
            return True  # Default to required if position is out of range
        
        # Calculate the position of this argument
        # Defaults are for the last N arguments where N = len(defaults)
        args_with_defaults = len(defaults)
        args_without_defaults = total_args - args_with_defaults
        
        # We need to figure out the position of this arg
        # This is a simplified approach - in practice we'd need the arg's position
        # For now, assume parameters without explicit Optional or default are required
        return True  # Will be refined based on actual default detection

    def _extract_return_type_schema(self, return_annotation: ast.AST, tree: ast.Module) -> dict[str, Any] | None:
        """Extract schema from function return type annotation."""
        if isinstance(return_annotation, ast.Name):
            # Simple type like str, int, or a class name
            if return_annotation.id in ["str", "int", "float", "bool", "list", "dict"]:
                return {"type": self._type_hint_to_json_type(return_annotation.id)}
            else:
                # Assume it's a Pydantic model class - look for it in the module
                return self._find_class_schema(return_annotation.id, tree)
        
        elif isinstance(return_annotation, ast.Subscript):
            # Complex type like list[dict], Optional[MyClass], etc.
            return self._extract_complex_type_schema(return_annotation)
        
        else:
            # Other complex types
            type_str = ast.unparse(return_annotation)
            return {"type": self._type_hint_to_json_type(type_str)}

    def _find_class_schema(self, class_name: str, tree: ast.Module) -> dict[str, Any] | None:
        """Find a class definition in the module and extract its schema."""
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # Check if it inherits from BaseModel
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "BaseModel":
                        return self._extract_pydantic_schema_from_ast(node)
        
        return None


def parse_project(project_path: Path) -> dict[ComponentType, list[ParsedComponent]]:
    """Parse a GolfMCP project to extract all components."""
    parser = AstParser(project_path)

    components: dict[ComponentType, list[ParsedComponent]] = {
        ComponentType.TOOL: [],
        ComponentType.RESOURCE: [],
        ComponentType.PROMPT: [],
    }

    # Parse each directory
    for comp_type, dir_name in [
        (ComponentType.TOOL, "tools"),
        (ComponentType.RESOURCE, "resources"),
        (ComponentType.PROMPT, "prompts"),
    ]:
        dir_path = project_path / dir_name
        if dir_path.exists() and dir_path.is_dir():
            dir_components = parser.parse_directory(dir_path)
            components[comp_type].extend(
                [c for c in dir_components if c.type == comp_type]
            )

    # Check for ID collisions
    all_ids = []
    for comp_type, comps in components.items():
        for comp in comps:
            if comp.name in all_ids:
                raise ValueError(
                    f"ID collision detected: {comp.name} is used by multiple components"
                )
            all_ids.append(comp.name)

    return components


def parse_common_files(project_path: Path) -> dict[str, Path]:
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
            if "__pycache__" in common_file.parts or any(
                part.startswith(".") for part in common_file.parts
            ):
                continue

            # Get the parent directory as the module path
            module_path = str(common_file.parent.relative_to(project_path))
            common_files[module_path] = common_file

    return common_files
