"""Command to run the built FastMCP server."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console

from golf.core.config import Settings

console = Console()


def run_server(
    project_path: Path,
    settings: Settings,
    dist_dir: Optional[Path] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
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
        console.print(f"[bold red]Error: Server file {server_path} not found.[/bold red]")
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
        
        return process.returncode
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user[/yellow]")
        return 0
    except Exception as e:
        console.print(f"\n[bold red]Error running server:[/bold red] {e}")
        return 1 