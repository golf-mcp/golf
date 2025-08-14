"""Platform registration for Golf MCP projects."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

from golf import __version__
from golf.core.config import Settings
from golf.core.parser import ComponentType, ParsedComponent

# Import endpoints with fallback for dev mode
try:
    # In built wheels, this exists (generated from _endpoints.py.in)
    from golf import _endpoints  # type: ignore
except ImportError:
    # In editable/dev installs, fall back to env-based values
    from golf import _endpoints_fallback as _endpoints  # type: ignore

console = Console()


async def register_project_with_platform(
    project_path: Path,
    settings: Settings,
    components: dict[ComponentType, list[ParsedComponent]],
) -> bool:
    """Register project with Golf platform during prod build.

    Args:
        project_path: Path to the project root
        settings: Project settings
        components: Parsed components dictionary

    Returns:
        True if registration succeeded or was skipped, False if failed
    """
    # Check if platform integration is enabled
    api_key = os.getenv("GOLF_API_KEY")
    if not api_key:
        return True  # Skip silently if no API key

    # Require explicit server ID
    server_id = os.getenv("GOLF_SERVER_ID")
    if not server_id:
        console.print(
            "[yellow]Warning: Platform registration skipped - GOLF_SERVER_ID environment variable required[/yellow]"
        )
        return True  # Skip registration but don't fail build

    # Build metadata payload
    metadata = {
        "project_name": settings.name,
        "description": settings.description,
        "server_id": server_id,
        "components": _build_component_list(components, project_path),
        "build_timestamp": datetime.utcnow().isoformat(),
        "golf_version": __version__,
        "component_counts": _get_component_counts(components),
        "server_config": {
            "host": settings.host,
            "port": settings.port,
            "transport": settings.transport,
            "auth_enabled": bool(settings.auth),
            "telemetry_enabled": settings.opentelemetry_enabled,
            "health_check_enabled": settings.health_check_enabled,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                _endpoints.PLATFORM_API_URL,
                json=metadata,
                headers={
                    "X-Golf-Key": api_key,
                    "Content-Type": "application/json",
                    "User-Agent": f"Golf-MCP/{__version__}",
                },
            )
            response.raise_for_status()

        console.print("[green]✓[/green] Registered with Golf platform")
        return True

    except httpx.TimeoutException:
        console.print("[yellow]Warning: Platform registration timed out[/yellow]")
        return False
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            console.print("[yellow]Warning: Platform registration failed - invalid API key[/yellow]")
        elif e.response.status_code == 403:
            console.print("[yellow]Warning: Platform registration failed - access denied[/yellow]")
        else:
            console.print(f"[yellow]Warning: Platform registration failed - HTTP {e.response.status_code}[/yellow]")
        return False
    except Exception as e:
        console.print(f"[yellow]Warning: Platform registration failed: {e}[/yellow]")
        return False  # Don't fail the build


def _build_component_list(
    components: dict[ComponentType, list[ParsedComponent]],
    project_path: Path,
) -> list[dict[str, Any]]:
    """Convert parsed components to platform format.

    Args:
        components: Dictionary of parsed components by type
        project_path: Path to the project root

    Returns:
        List of component metadata dictionaries
    """
    result = []

    for comp_type, comp_list in components.items():
        for comp in comp_list:
            # Start with basic component data
            component_data = {
                "name": comp.name,
                "type": comp_type.value,
                "description": comp.docstring,
                "entry_function": comp.entry_function,
                "parent_module": comp.parent_module,
            }

            # Add file path relative to project root if available
            if comp.file_path:
                try:
                    file_path = Path(comp.file_path)
                    # Use the provided project_path for relative calculation
                    rel_path = file_path.relative_to(project_path)
                    component_data["file_path"] = str(rel_path)
                except ValueError:
                    # If relative_to fails, try to find a common path or use filename
                    component_data["file_path"] = Path(comp.file_path).name

            # Add schema information only if available and not None
            if hasattr(comp, "input_schema") and comp.input_schema:
                component_data["input_schema"] = comp.input_schema
            if hasattr(comp, "output_schema") and comp.output_schema:
                component_data["output_schema"] = comp.output_schema

            # Add component-specific fields only if they have values
            if comp_type == ComponentType.RESOURCE:
                if hasattr(comp, "uri_template") and comp.uri_template:
                    component_data["uri_template"] = comp.uri_template

            elif comp_type == ComponentType.TOOL:
                if hasattr(comp, "annotations") and comp.annotations:
                    component_data["annotations"] = comp.annotations

            # Add parameters only if they exist and are not empty
            if hasattr(comp, "parameters") and comp.parameters:
                component_data["parameters"] = comp.parameters

            result.append(component_data)

    return result


def _get_component_counts(
    components: dict[ComponentType, list[ParsedComponent]],
) -> dict[str, int]:
    """Get component counts by type.

    Args:
        components: Dictionary of parsed components by type

    Returns:
        Dictionary with counts for each component type
    """
    return {
        "tools": len(components.get(ComponentType.TOOL, [])),
        "resources": len(components.get(ComponentType.RESOURCE, [])),
        "prompts": len(components.get(ComponentType.PROMPT, [])),
        "total": sum(len(comp_list) for comp_list in components.values()),
    }
