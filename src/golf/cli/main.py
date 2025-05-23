"""CLI entry points for GolfMCP."""

import os
from pathlib import Path
from typing import Optional
import atexit

import typer
from rich.console import Console
from rich.panel import Panel

from golf import __version__
from golf.core.config import load_settings, find_project_root
from golf.core.telemetry import is_telemetry_enabled, shutdown, set_telemetry_enabled, track_event

# Create console for rich output
console = Console()

# Create the typer app instance
app = typer.Typer(
    name="golf",
    help="GolfMCP: A Pythonic framework for building MCP servers with zero boilerplate",
    add_completion=False,
)

# Register telemetry shutdown on exit
atexit.register(shutdown)


def _version_callback(value: bool) -> None:
    """Print version and exit if --version flag is used."""
    if value:
        console.print(f"GolfMCP v{__version__}")
        raise typer.Exit()


@app.callback()
def callback(
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Increase verbosity of output."
    ),
    no_telemetry: bool = typer.Option(
        False, "--no-telemetry", help="Disable telemetry collection (persists for future commands)."
    ),
) -> None:
    """GolfMCP: A Pythonic framework for building MCP servers with zero boilerplate."""
    # Set verbosity in environment for other components to access
    if verbose:
        os.environ["GOLF_VERBOSE"] = "1"
    
    # Set telemetry preference if flag is used
    if no_telemetry:
        set_telemetry_enabled(False, persist=True)
        console.print("[dim]Telemetry has been disabled. You can re-enable it with: golf telemetry enable[/dim]")


@app.command()
def init(
    project_name: str = typer.Argument(..., help="Name of the project to create"),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Directory to create the project in"
    ),
    template: str = typer.Option(
        "basic", "--template", "-t", help="Template to use (basic or api_key)"
    ),
) -> None:
    """Initialize a new GolfMCP project.
    
    Creates a new directory with the project scaffold, including
    examples for tools, resources, and prompts.
    """
    # Import here to avoid circular imports
    from golf.commands.init import initialize_project
    
    # Use the current directory if no output directory is specified
    if output_dir is None:
        output_dir = Path.cwd() / project_name
    
    # Execute the initialization command (it handles its own tracking)
    initialize_project(project_name=project_name, output_dir=output_dir, template=template)


# Create a build group with subcommands
build_app = typer.Typer(help="Build a standalone FastMCP application")
app.add_typer(build_app, name="build")


@build_app.command("dev")
def build_dev(
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", "-o", help="Directory to output the built project"
    )
):
    """Build a development version with environment variables copied."""
    # Find project root directory
    project_root, config_path = find_project_root()
    
    if not project_root:
        console.print("[bold red]Error: No GolfMCP project found in the current directory or any parent directory.[/bold red]")
        console.print("Run 'golf init <project_name>' to create a new project.")
        track_event("cli_build_failed", {"success": False, "environment": "dev"})
        raise typer.Exit(code=1)
    
    # Load settings from the found project
    settings = load_settings(project_root)
    
    # Set default output directory if not specified
    if output_dir is None:
        output_dir = project_root / "dist"
    else:
        output_dir = Path(output_dir)
    
    try:
        # Build the project with environment variables copied
        from golf.commands.build import build_project
        build_project(project_root, settings, output_dir, build_env="dev", copy_env=True)
        # Track successful build with environment
        track_event("cli_build_success", {"success": True, "environment": "dev"})
    except Exception:
        track_event("cli_build_failed", {"success": False, "environment": "dev"})
        raise


@build_app.command("prod")
def build_prod(
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", "-o", help="Directory to output the built project"
    )
):
    """Build a production version without copying environment variables."""
    # Find project root directory
    project_root, config_path = find_project_root()
    
    if not project_root:
        console.print("[bold red]Error: No GolfMCP project found in the current directory or any parent directory.[/bold red]")
        console.print("Run 'golf init <project_name>' to create a new project.")
        track_event("cli_build_failed", {"success": False, "environment": "prod"})
        raise typer.Exit(code=1)
    
    # Load settings from the found project
    settings = load_settings(project_root)
    
    # Set default output directory if not specified
    if output_dir is None:
        output_dir = project_root / "dist"
    else:
        output_dir = Path(output_dir)
    
    try:
        # Build the project without copying environment variables
        from golf.commands.build import build_project
        build_project(project_root, settings, output_dir, build_env="prod", copy_env=False)
        # Track successful build with environment
        track_event("cli_build_success", {"success": True, "environment": "prod"})
    except Exception:
        track_event("cli_build_failed", {"success": False, "environment": "prod"})
        raise


@app.command()
def run(
    dist_dir: Optional[str] = typer.Option(
        None, "--dist-dir", "-d", help="Directory containing the built server"
    ),
    host: Optional[str] = typer.Option(
        None, "--host", "-h", help="Host to bind to (overrides settings)"
    ),
    port: Optional[int] = typer.Option(
        None, "--port", "-p", help="Port to bind to (overrides settings)"
    ),
    build_first: bool = typer.Option(
        True, "--build/--no-build", help="Build the project before running"
    ),
):
    """Run the built FastMCP server.
    
    This command runs the built server from the dist directory.
    By default, it will build the project first if needed.
    """
    # Find project root directory
    project_root, config_path = find_project_root()
    
    if not project_root:
        console.print("[bold red]Error: No GolfMCP project found in the current directory or any parent directory.[/bold red]")
        console.print("Run 'golf init <project_name>' to create a new project.")
        track_event("cli_run_failed", {"success": False})
        raise typer.Exit(code=1)
    
    # Load settings from the found project
    settings = load_settings(project_root)
    
    # Set default dist directory if not specified
    if dist_dir is None:
        dist_dir = project_root / "dist"
    else:
        dist_dir = Path(dist_dir)
    
    # Check if dist directory exists
    if not dist_dir.exists():
        if build_first:
            console.print(f"[yellow]Dist directory {dist_dir} not found. Building first...[/yellow]")
            # Build the project
            from golf.commands.build import build_project
            build_project(project_root, settings, dist_dir)
        else:
            console.print(f"[bold red]Error: Dist directory {dist_dir} not found.[/bold red]")
            console.print("Run 'golf build' first or use --build to build automatically.")
            track_event("cli_run_failed", {"success": False})
            raise typer.Exit(code=1)
    
    try:
        # Import and run the server
        from golf.commands.run import run_server
        return_code = run_server(
            project_path=project_root,
            settings=settings,
            dist_dir=dist_dir,
            host=host,
            port=port
        )
        
        # Track based on return code
        if return_code == 0:
            track_event("cli_run_success", {"success": True})
        else:
            track_event("cli_run_failed", {"success": False})
        
        # Exit with the same code as the server
        if return_code != 0:
            raise typer.Exit(code=return_code)
    except Exception:
        track_event("cli_run_failed", {"success": False})
        raise


# Add telemetry command group
@app.command()
def telemetry(
    action: str = typer.Argument(..., help="Action to perform: 'enable' or 'disable'")
):
    """Manage telemetry settings."""
    if action.lower() == "enable":
        set_telemetry_enabled(True, persist=True)
        console.print("[green]✓[/green] Telemetry enabled. Thank you for helping improve Golf!")
    elif action.lower() == "disable":
        set_telemetry_enabled(False, persist=True)
        console.print("[yellow]Telemetry disabled.[/yellow] You can re-enable it anytime with: golf telemetry enable")
    else:
        console.print(f"[red]Unknown action '{action}'. Use 'enable' or 'disable'.[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    # Show welcome banner when run directly
    console.print(
        Panel.fit(
            f"[bold green]GolfMCP[/bold green] v{__version__}\n"
            "[dim]A Pythonic framework for building MCP servers[/dim]",
            border_style="green",
        )
    )
    
    # Add telemetry notice if enabled
    if is_telemetry_enabled():
        console.print(
            "[dim]📊 Anonymous usage data is collected to improve Golf. "
            "Disable with: golf telemetry disable[/dim]\n"
        )
    
    # Run the CLI app
    app() 