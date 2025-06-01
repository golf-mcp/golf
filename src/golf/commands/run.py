"""Command to run the built FastMCP server."""

import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console

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
        dist_dir: Path to the directory containing the built server (defaults to project_path/dist)
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
        console.print(
            f"[bold red]Error: Server file {server_path} not found.[/bold red]"
        )
        return 1

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
        if process.returncode == 0:
            console.print("[green]Server stopped successfully[/green]")
        elif process.returncode == 130:
            console.print("[yellow]Server stopped by user interrupt (Ctrl+C)[/yellow]")
        elif process.returncode == 143:
            console.print(
                "[yellow]Server stopped by SIGTERM (graceful shutdown)[/yellow]"
            )
        elif process.returncode == 137:
            console.print(
                "[yellow]Server stopped by SIGKILL (forced shutdown)[/yellow]"
            )
        elif process.returncode in [1, 2]:
            console.print(
                f"[red]Server exited with error code {process.returncode}[/red]"
            )
        else:
            console.print(
                f"[orange]Server exited with code {process.returncode}[/orange]"
            )

        return process.returncode
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user (Ctrl+C)[/yellow]")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        console.print(f"\n[bold red]Error running server:[/bold red] {e}")
        return 1
