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
            if "__pycache__" in file_path.parts or any(part.startswith(".") for part in file_path.parts):
                continue

            try:
                file_components = self.parse_file(file_path)
                components.extend(file_components)
            except Exception as e:
                relative_path = file_path.relative_to(self.project_root)
                console.print(f"[bold red]Error parsing {relative_path}:[/bold red] {e}")

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
                    if isinstance(target, ast.Name) and target.id == "export" and isinstance(node.value, ast.Name):
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
            entry_function=export_target or "run",  # Store the name of the entry function
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

    def _process_entry_function(
        self,
        component: ParsedComponent,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        tree: ast.Module,
        file_path: Path,
    ) -> None:
        """Process the entry function to extract parameters and return type."""
        # Check for return annotation - STRICT requirement
        if func_node.returns is None:
            raise ValueError(f"Missing return annotation for {func_node.name} function in {file_path}")

        # Extract parameter names for basic info
        parameters = []
        for arg in func_node.args.args:
            # Skip self, cls, ctx parameters
            if arg.arg not in ("self", "cls", "ctx"):
                parameters.append(arg.arg)

        # Store parameters
        component.parameters = parameters

        # Extract schemas using runtime inspection (safer and more accurate)
        try:
            self._extract_schemas_at_runtime(component, file_path)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not extract schemas from {file_path}: {e}[/yellow]")
            # Continue without schemas - better than failing the build

    def _extract_schemas_at_runtime(self, component: ParsedComponent, file_path: Path) -> None:
        """Extract input/output schemas by importing and inspecting the
        actual function."""
        import importlib.util
        import sys

        # Convert file path to module name
        rel_path = file_path.relative_to(self.project_root)
        module_name = str(rel_path.with_suffix("")).replace("/", ".")

        # Temporarily add project root to sys.path
        project_root_str = str(self.project_root)
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)
            cleanup_path = True
        else:
            cleanup_path = False

        try:
            # Import the module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get the entry function
            if not hasattr(module, component.entry_function):
                return

            func = getattr(module, component.entry_function)

            # Extract input schema from function signature
            component.input_schema = self._extract_input_schema(func)

            # Extract output schema from return type annotation
            component.output_schema = self._extract_output_schema(func)

        finally:
            # Clean up sys.path
            if cleanup_path and project_root_str in sys.path:
                sys.path.remove(project_root_str)

    def _extract_input_schema(self, func: Any) -> dict[str, Any] | None:
        """Extract input schema from function signature using runtime inspection."""
        import inspect
        from typing import get_type_hints

        try:
            sig = inspect.signature(func)
            type_hints = get_type_hints(func, include_extras=True)

            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                # Skip special parameters
                if param_name in ("self", "cls", "ctx"):
                    continue

                # Get type hint
                if param_name not in type_hints:
                    continue

                type_hint = type_hints[param_name]

                # Extract schema for this parameter
                param_schema = self._extract_param_schema_from_hint(type_hint, param_name)
                if param_schema:
                    # Clean the schema to remove problematic objects
                    cleaned_schema = self._clean_schema(param_schema)
                    if cleaned_schema:
                        properties[param_name] = cleaned_schema

                        # Check if required (no default value)
                        if param.default is param.empty:
                            required.append(param_name)

            if properties:
                return {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }

        except Exception as e:
            console.print(f"[yellow]Warning: Could not extract input schema: {e}[/yellow]")

        return None

    def _extract_output_schema(self, func: Any) -> dict[str, Any] | None:
        """Extract output schema from return type annotation."""
        from typing import get_type_hints

        try:
            type_hints = get_type_hints(func, include_extras=True)
            return_type = type_hints.get("return")

            if return_type is None:
                return None

            # If it's a Pydantic BaseModel, extract schema manually
            if hasattr(return_type, "model_fields"):
                return self._extract_pydantic_model_schema(return_type)

            # For other types, create a simple schema
            return self._type_to_schema(return_type)

        except Exception as e:
            console.print(f"[yellow]Warning: Could not extract output schema: {e}[/yellow]")

        return None

    def _extract_pydantic_model_schema(self, model_class: Any) -> dict[str, Any]:
        """Extract schema from Pydantic model by inspecting fields directly."""
        try:
            schema = {"type": "object", "properties": {}, "required": []}

            if hasattr(model_class, "model_fields"):
                for field_name, field_info in model_class.model_fields.items():
                    # Extract field type
                    field_type = field_info.annotation if hasattr(field_info, "annotation") else None
                    if field_type:
                        field_schema = self._type_to_schema(field_type)

                        # Add description if available
                        if hasattr(field_info, "description") and field_info.description:
                            field_schema["description"] = field_info.description

                        # Add title
                        field_schema["title"] = field_name.replace("_", " ").title()

                        # Add default if available
                        if hasattr(field_info, "default") and field_info.default is not None:
                            try:
                                # Only add if it's JSON serializable
                                import json

                                json.dumps(field_info.default)
                                field_schema["default"] = field_info.default
                            except:
                                pass

                        schema["properties"][field_name] = field_schema

                        # Check if required
                        if hasattr(field_info, "is_required") and field_info.is_required():
                            schema["required"].append(field_name)
                        elif not hasattr(field_info, "default") or field_info.default is None:
                            # Assume required if no default
                            schema["required"].append(field_name)

            return schema

        except Exception as e:
            console.print(f"[yellow]Warning: Could not extract Pydantic model schema: {e}[/yellow]")
            return {"type": "object"}

    def _clean_schema(self, schema: Any) -> dict[str, Any]:
        """Clean up a schema to remove non-JSON-serializable objects."""
        import json

        def clean_object(obj: Any) -> Any:
            if obj is None:
                return None
            elif isinstance(obj, (str, int, float, bool)):
                return obj
            elif isinstance(obj, dict):
                cleaned = {}
                for k, v in obj.items():
                    # Skip problematic keys
                    if k in ["definitions", "$defs", "allOf", "anyOf", "oneOf"]:
                        continue
                    cleaned_v = clean_object(v)
                    if cleaned_v is not None:
                        cleaned[k] = cleaned_v
                return cleaned if cleaned else None
            elif isinstance(obj, list):
                cleaned = []
                for item in obj:
                    cleaned_item = clean_object(item)
                    if cleaned_item is not None:
                        cleaned.append(cleaned_item)
                return cleaned if cleaned else None
            else:
                # For any other type, test JSON serializability
                try:
                    json.dumps(obj)
                    return obj
                except (TypeError, ValueError):
                    # If it's not JSON serializable, try to get a string representation
                    if hasattr(obj, "__name__"):
                        return obj.__name__
                    elif hasattr(obj, "__str__"):
                        try:
                            str_val = str(obj)
                            if str_val and str_val != repr(obj):
                                return str_val
                        except:
                            pass
                    return None

        cleaned = clean_object(schema)
        return cleaned if cleaned else {"type": "object"}

    def _extract_param_schema_from_hint(self, type_hint: Any, param_name: str) -> dict[str, Any] | None:
        """Extract parameter schema from type hint (including Annotated types)."""
        from typing import get_args, get_origin

        # Handle Annotated types
        if get_origin(type_hint) is not None:
            origin = get_origin(type_hint)
            args = get_args(type_hint)

            # Check for Annotated[Type, Field(...)]
            if hasattr(origin, "__name__") and origin.__name__ == "Annotated" and len(args) >= 2:
                base_type = args[0]
                metadata = args[1:]

                # Start with base type schema
                schema = self._type_to_schema(base_type)

                # Extract Field metadata
                for meta in metadata:
                    if hasattr(meta, "description") and meta.description:
                        schema["description"] = meta.description
                    if hasattr(meta, "title") and meta.title:
                        schema["title"] = meta.title
                    if hasattr(meta, "default") and meta.default is not None:
                        schema["default"] = meta.default
                    # Add other Field constraints as needed

                return schema

        # For non-Annotated types, just convert the type
        return self._type_to_schema(type_hint)

    def _type_to_schema(self, type_hint: object) -> dict[str, Any]:
        """Convert a Python type to JSON schema."""
        from typing import get_args, get_origin
        import types

        # Handle None/NoneType
        if type_hint is type(None):
            return {"type": "null"}

        # Handle basic types
        if type_hint is str:
            return {"type": "string"}
        elif type_hint is int:
            return {"type": "integer"}
        elif type_hint is float:
            return {"type": "number"}
        elif type_hint is bool:
            return {"type": "boolean"}
        elif type_hint is list:
            return {"type": "array"}
        elif type_hint is dict:
            return {"type": "object"}

        # Handle generic types
        origin = get_origin(type_hint)
        if origin is not None:
            args = get_args(type_hint)

            if origin is list:
                if args:
                    item_schema = self._type_to_schema(args[0])
                    return {"type": "array", "items": item_schema}
                return {"type": "array"}

            elif origin is dict:
                return {"type": "object"}

            elif (
                origin is types.UnionType
                or (hasattr(types, "UnionType") and origin is types.UnionType)
                or str(origin).startswith("typing.Union")
            ):
                # Handle Union types (including Optional)
                non_none_types = [arg for arg in args if arg is not type(None)]
                if len(non_none_types) == 1:
                    # This is Optional[Type]
                    return self._type_to_schema(non_none_types[0])
                # For complex unions, default to object
                return {"type": "object"}

        # For unknown types, try to use Pydantic schema if available
        if hasattr(type_hint, "model_json_schema"):
            schema = type_hint.model_json_schema()
            return self._clean_schema(schema)

        # Default fallback
        return {"type": "object"}

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
                    component.input_schema = self._extract_pydantic_schema_from_ast(input_class)
                    break

        # Process Output class if found
        if output_class:
            # Check if it inherits from BaseModel
            for base in output_class.bases:
                if isinstance(base, ast.Name) and base.id == "BaseModel":
                    component.output_schema = self._extract_pydantic_schema_from_ast(output_class)
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
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "resource_uri"
                        and isinstance(node.value, ast.Constant)
                    ):
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

        Following the spec: <filename> + ("_" + "_".join(PathRev) if PathRev else "")
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
            return f"{filename}_{'_'.join(parent_dirs)}"
        else:
            return filename

    def _extract_pydantic_schema_from_ast(self, class_node: ast.ClassDef) -> dict[str, Any]:
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

                # Create property definition using improved type extraction
                if isinstance(node.annotation, ast.Subscript):
                    # Use the improved complex type extraction
                    type_schema = self._extract_complex_type_schema(node.annotation)
                    if isinstance(type_schema, dict) and "type" in type_schema:
                        prop = type_schema.copy()
                        prop["title"] = field_name.replace("_", " ").title()
                    else:
                        prop = {
                            "type": self._type_hint_to_json_type(annotation),
                            "title": field_name.replace("_", " ").title(),
                        }
                elif isinstance(node.annotation, ast.Name):
                    prop = {
                        "type": self._type_hint_to_json_type(node.annotation.id),
                        "title": field_name.replace("_", " ").title(),
                    }
                else:
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
                            if keyword.arg == "default" or keyword.arg == "default_factory":
                                if isinstance(keyword.value, ast.Constant):
                                    prop["default"] = keyword.value.value
                            elif keyword.arg == "description":
                                if isinstance(keyword.value, ast.Constant):
                                    prop["description"] = keyword.value.value
                            elif keyword.arg == "title":
                                if isinstance(keyword.value, ast.Constant):
                                    prop["title"] = keyword.value.value

                        # Check for position default argument
                        # (Field(..., "description"))
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
                    elif (
                        isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == "Field"
                    ):
                        # Field has default if it doesn't use ... or if it has a
                        # default keyword
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
            "any": "object",  # Any maps to object
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
            elif isinstance(value, ast.NameConstant):  # For older Python versions (True/False/None)
                result[key_str] = value.value
            elif isinstance(value, ast.Name):
                # Handle True/False/None as names
                if value.id in ("True", "False", "None"):
                    result[key_str] = {"True": True, "False": False, "None": None}[value.id]
            # We could add more complex value handling here if needed

        return result

    def _extract_complex_type_schema(self, subscript: ast.Subscript) -> dict[str, Any]:
        """Extract schema from complex types like list[str], dict[str, Any], etc."""
        if isinstance(subscript.value, ast.Name):
            base_type = subscript.value.id

            if base_type == "list":
                # Handle list[ItemType]
                if isinstance(subscript.slice, ast.Name):
                    item_type = self._type_hint_to_json_type(subscript.slice.id)
                    return {"type": "array", "items": {"type": item_type}}
                elif isinstance(subscript.slice, ast.Subscript):
                    # Nested subscript like list[dict[str, Any]]
                    item_schema = self._extract_complex_type_schema(subscript.slice)
                    return {"type": "array", "items": item_schema}
                else:
                    # Complex item type, try to parse it
                    item_type_str = ast.unparse(subscript.slice)
                    if "dict" in item_type_str.lower():
                        return {"type": "array", "items": {"type": "object"}}
                    else:
                        item_type = self._type_hint_to_json_type(item_type_str)
                        return {"type": "array", "items": {"type": item_type}}

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

        # If there are no defaults, all parameters are required
        if not defaults:
            return True

        # Defaults apply to the last N parameters where N = len(defaults)
        # So if we have 4 args and 2 defaults, defaults apply to args[2] and args[3]
        args_with_defaults = len(defaults)
        first_default_position = total_args - args_with_defaults

        # If this parameter's position is before the first default position,
        # it's required
        return position < first_default_position

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
            components[comp_type].extend([c for c in dir_components if c.type == comp_type])

    # Check for ID collisions
    all_ids = []
    for comp_type, comps in components.items():
        for comp in comps:
            if comp.name in all_ids:
                raise ValueError(f"ID collision detected: {comp.name} is used by multiple components")
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
            if "__pycache__" in common_file.parts or any(part.startswith(".") for part in common_file.parts):
                continue

            # Get the parent directory as the module path
            module_path = str(common_file.parent.relative_to(project_path))
            common_files[module_path] = common_file

    return common_files


def _is_golf_component_file(file_path: Path) -> bool:
    """Check if a Python file is a Golf component (has export or resource_uri).

    Args:
        file_path: Path to the Python file to check

    Returns:
        True if the file appears to be a Golf component, False otherwise
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Parse the file to check for Golf component patterns
        tree = ast.parse(content)

        # Look for 'export' or 'resource_uri' variable assignments
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id in ("export", "resource_uri"):
                            return True

        return False

    except (SyntaxError, OSError, UnicodeDecodeError):
        # If we can't parse the file, assume it's not a component
        return False


def parse_shared_files(project_path: Path) -> dict[str, Path]:
    """Find all shared Python files in the project (non-component .py files).

    Args:
        project_path: Path to the project root

    Returns:
        Dictionary mapping module paths to shared file paths
    """
    shared_files = {}

    # Search for all .py files in tools, resources, and prompts directories
    for dir_name in ["tools", "resources", "prompts"]:
        base_dir = project_path / dir_name
        if not base_dir.exists() or not base_dir.is_dir():
            continue

        # Find all .py files (recursively)
        for py_file in base_dir.glob("**/*.py"):
            # Skip files in __pycache__ or other hidden directories
            if "__pycache__" in py_file.parts or any(part.startswith(".") for part in py_file.parts):
                continue

            # Skip files that are Golf components (have export or resource_uri)
            if _is_golf_component_file(py_file):
                continue

            # Calculate the module path for this shared file
            # For example: tools/weather/helpers.py -> tools/weather/helpers
            relative_path = py_file.relative_to(project_path)
            module_path = str(relative_path.with_suffix(""))  # Remove .py extension

            shared_files[module_path] = py_file

    return shared_files
