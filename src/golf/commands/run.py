"""Command to run the built FastMCP server."""

import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.text import Text

from golf.cli.branding import create_command_header, get_status_text, STATUS_ICONS, GOLF_BLUE, GOLF_GREEN, GOLF_ORANGE
from golf.core.config import Settings

console = Console()


def run_server(
    project_path: Path,
    settings: Settings,
    dist_dir: Path | None = None,
    host: str | None = None,
    port: int | None = None,
) -> int:
    """Run the built FastMCP server.

    Args:
        project_path: Path to the project root
        settings: Project settings
        dist_dir: Path to the directory containing the built server
            (defaults to project_path/dist)
        host: Host to bind the server to (overrides settings)
        port: Port to bind the server to (overrides settings)

    Returns:
        Process return code
    """
    # Set default dist directory if not specified
    if dist_dir is None:
        dist_dir = project_path / "dist"

    # Check if server file exists
    server_path = dist_dir / "server.py"
    if not server_path.exists():
        console.print(get_status_text("error", f"Server file {server_path} not found"))
        return 1

    # Display server startup header
    create_command_header("Starting Server", f"{settings.name}", console)

    # Show server info with flashy styling
    server_host = host or settings.host or "localhost"
    server_port = port or settings.port or 3000

    server_content = Text()
    server_content.append("🚀 ", style=f"bold {GOLF_ORANGE}")
    server_content.append(f"{STATUS_ICONS['server']} Server starting on ", style=f"bold {GOLF_BLUE}")
    server_content.append(f"http://{server_host}:{server_port}", style=f"bold {GOLF_GREEN}")
    server_content.append(" 🚀", style=f"bold {GOLF_ORANGE}")
    server_content.append("\n")

    # Add telemetry status indicator
    if settings.opentelemetry_enabled:
        server_content.append("📊 Golf telemetry enabled", style=f"dim {GOLF_BLUE}")
        server_content.append("\n")

    server_content.append("⚡ Press Ctrl+C to stop ⚡", style=f"dim {GOLF_ORANGE}")

    console.print(
        Panel(
            Align.center(server_content),
            border_style=GOLF_BLUE,
            padding=(1, 2),
            title="[bold]🌐 SERVER READY 🌐[/bold]",
            title_align="center",
        )
    )
    console.print()

    # Prepare environment variables
    env = os.environ.copy()
    if host is not None:
        env["HOST"] = host
    elif settings.host:
        env["HOST"] = settings.host

    if port is not None:
        env["PORT"] = str(port)
    elif settings.port:
        env["PORT"] = str(settings.port)

    # Run the server
    try:
        # Using subprocess to properly handle signals (Ctrl+C)
        process = subprocess.run(
            [sys.executable, str(server_path)],
            cwd=dist_dir,
            env=env,
        )

        # Provide more context about the exit
        console.print()
        if process.returncode == 0:
            console.print(get_status_text("success", "Server stopped successfully"))
        elif process.returncode == 130:
            console.print(get_status_text("info", "Server stopped by user interrupt (Ctrl+C)"))
        elif process.returncode == 143:
            console.print(get_status_text("info", "Server stopped by SIGTERM (graceful shutdown)"))
        elif process.returncode == 137:
            console.print(get_status_text("warning", "Server stopped by SIGKILL (forced shutdown)"))
        elif process.returncode in [1, 2]:
            console.print(get_status_text("error", f"Server exited with error code {process.returncode}"))
        else:
            console.print(get_status_text("warning", f"Server exited with code {process.returncode}"))

        return process.returncode
    except KeyboardInterrupt:
        console.print()
        console.print(get_status_text("info", "Server stopped by user (Ctrl+C)"))
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        console.print()
        console.print(get_status_text("error", f"Error running server: {e}"))
        return 1
