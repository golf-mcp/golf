"""CLI entry points for GolfMCP."""

import atexit
import os
from pathlib import Path

import typer
from rich.console import Console

from golf import __version__
from golf.cli.branding import create_welcome_banner, create_command_header
from golf.core.config import find_project_root, load_settings
from golf.core.telemetry import (
    is_telemetry_enabled,
    set_telemetry_enabled,
    shutdown,
    track_event,
    track_detailed_error,
)

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
        create_welcome_banner(__version__, console)
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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Increase verbosity of output."),
    no_telemetry: bool = typer.Option(
        False,
        "--no-telemetry",
        help="Disable telemetry collection (persists for future commands).",
    ),
    test: bool = typer.Option(
        False,
        "--test",
        hidden=True,
        help="Run in test mode (disables telemetry for this execution only).",
    ),
) -> None:
    """GolfMCP: A Pythonic framework for building MCP servers with zero boilerplate."""
    # Set verbosity in environment for other components to access
    if verbose:
        os.environ["GOLF_VERBOSE"] = "1"

    # Set test mode if flag is used (temporary, just for this execution)
    if test:
        set_telemetry_enabled(False, persist=False)
        os.environ["GOLF_TEST_MODE"] = "1"

    # Set telemetry preference if flag is used (permanent)
    if no_telemetry:
        set_telemetry_enabled(False, persist=True)
        console.print("[dim]Telemetry has been disabled. You can re-enable it with: golf telemetry enable[/dim]")


@app.command()
def init(
    project_name: str = typer.Argument(..., help="Name of the project to create"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Directory to create the project in"),
) -> None:
    """Initialize a new GolfMCP project.

    Creates a new directory with the project scaffold, including
    examples for tools, resources, and prompts.
    """
    # Show the Golf logo for project initialization
    create_welcome_banner(__version__, console)
    console.print()
    create_command_header("Initialize Project", f"Creating {project_name}", console)

    # Import here to avoid circular imports
    from golf.commands.init import initialize_project

    # Use the current directory if no output directory is specified
    if output_dir is None:
        output_dir = Path.cwd() / project_name

    # Execute the initialization command (it handles its own tracking)
    initialize_project(project_name=project_name, output_dir=output_dir)


# Create a build group with subcommands
build_app = typer.Typer(help="Build a standalone FastMCP application")
app.add_typer(build_app, name="build")


@build_app.command("dev")
def build_dev(
    output_dir: str | None = typer.Option(None, "--output-dir", "-o", help="Directory to output the built project"),
) -> None:
    """Build a development version with app environment variables copied.

    Golf credentials (GOLF_*) are always loaded from .env for build operations.
    All environment variables are copied to the built project for development.
    """
    # Find project root directory
    project_root, config_path = find_project_root()

    if not project_root:
        console.print(
            "[bold red]Error: No GolfMCP project found in the current directory or any parent directory.[/bold red]"
        )
        console.print("Run 'golf init <project_name>' to create a new project.")
        track_event(
            "cli_build_failed",
            {
                "success": False,
                "environment": "dev",
                "error_type": "NoProjectFound",
                "error_message": "No GolfMCP project found",
            },
        )
        raise typer.Exit(code=1)

    # Load settings from the found project
    settings = load_settings(project_root)

    # Set default output directory if not specified
    output_dir = project_root / "dist" if output_dir is None else Path(output_dir)

    try:
        # Build the project with environment variables copied
        from golf.commands.build import build_project

        build_project(project_root, settings, output_dir, build_env="dev", copy_env=True)
        # Track successful build with environment
        track_event("cli_build_success", {"success": True, "environment": "dev"})
    except Exception as e:
        track_detailed_error(
            "cli_build_failed",
            e,
            context="Development build with environment variables",
            operation="build_dev",
            additional_props={"environment": "dev", "copy_env": True},
        )
        raise


@build_app.command("prod")
def build_prod(
    output_dir: str | None = typer.Option(None, "--output-dir", "-o", help="Directory to output the built project"),
) -> None:
    """Build a production version for deployment.

    Golf credentials (GOLF_*) are always loaded from .env for build operations
    (platform registration, resource updates). App environment variables are
    NOT copied for security - provide them in your deployment environment.

    Your production deployment must include GOLF_* vars for runtime telemetry.
    """
    # Find project root directory
    project_root, config_path = find_project_root()

    if not project_root:
        console.print(
            "[bold red]Error: No GolfMCP project found in the current directory or any parent directory.[/bold red]"
        )
        console.print("Run 'golf init <project_name>' to create a new project.")
        track_event(
            "cli_build_failed",
            {
                "success": False,
                "environment": "prod",
                "error_type": "NoProjectFound",
                "error_message": "No GolfMCP project found",
            },
        )
        raise typer.Exit(code=1)

    # Load settings from the found project
    settings = load_settings(project_root)

    # Set default output directory if not specified
    output_dir = project_root / "dist" if output_dir is None else Path(output_dir)

    try:
        # Build the project without copying environment variables
        from golf.commands.build import build_project

        build_project(project_root, settings, output_dir, build_env="prod", copy_env=False)
        # Track successful build with environment
        track_event("cli_build_success", {"success": True, "environment": "prod"})
    except Exception as e:
        track_detailed_error(
            "cli_build_failed",
            e,
            context="Production build without environment variables",
            operation="build_prod",
            additional_props={"environment": "prod", "copy_env": False},
        )
        raise


@app.command()
def run(
    dist_dir: str | None = typer.Option(None, "--dist-dir", "-d", help="Directory containing the built server"),
    host: str | None = typer.Option(None, "--host", "-h", help="Host to bind to (overrides settings)"),
    port: int | None = typer.Option(None, "--port", "-p", help="Port to bind to (overrides settings)"),
    build_first: bool = typer.Option(True, "--build/--no-build", help="Build the project before running"),
) -> None:
    """Run the built FastMCP server.

    This command runs the built server from the dist directory.
    By default, it will build the project first if needed.
    """
    # Find project root directory
    project_root, config_path = find_project_root()

    if not project_root:
        console.print(
            "[bold red]Error: No GolfMCP project found in the current directory or any parent directory.[/bold red]"
        )
        console.print("Run 'golf init <project_name>' to create a new project.")
        track_event(
            "cli_run_failed",
            {
                "success": False,
                "error_type": "NoProjectFound",
                "error_message": "No GolfMCP project found",
            },
        )
        raise typer.Exit(code=1)

    # Load settings from the found project
    settings = load_settings(project_root)

    # Set default dist directory if not specified
    dist_dir = project_root / "dist" if dist_dir is None else Path(dist_dir)

    # Check if dist directory exists
    if not dist_dir.exists():
        if build_first:
            console.print(f"[yellow]Dist directory {dist_dir} not found. Building first...[/yellow]")
            try:
                # Build the project
                from golf.commands.build import build_project

                build_project(project_root, settings, dist_dir)
            except Exception as e:
                console.print(f"[bold red]Error building project:[/bold red] {str(e)}")
                track_detailed_error(
                    "cli_run_failed",
                    e,
                    context="Auto-build before running server",
                    operation="auto_build_before_run",
                    additional_props={"auto_build": True},
                )
                raise
        else:
            console.print(f"[bold red]Error: Dist directory {dist_dir} not found.[/bold red]")
            console.print("Run 'golf build' first or use --build to build automatically.")
            track_event(
                "cli_run_failed",
                {
                    "success": False,
                    "error_type": "DistNotFound",
                    "error_message": "Dist directory not found",
                },
            )
            raise typer.Exit(code=1)

    try:
        # Import and run the server
        from golf.commands.run import run_server

        return_code = run_server(
            project_path=project_root,
            settings=settings,
            dist_dir=dist_dir,
            host=host,
            port=port,
        )

        # Track based on return code with better categorization
        if return_code == 0:
            track_event("cli_run_success", {"success": True})
        elif return_code in [130, 143, 137, 2]:
            # Intentional shutdowns (not errors):
            # 130: Ctrl+C (SIGINT)
            # 143: SIGTERM (graceful shutdown, e.g., Kubernetes, Docker)
            # 137: SIGKILL (forced shutdown)
            # 2: General interrupt/graceful shutdown
            shutdown_type = {
                130: "UserInterrupt",
                143: "GracefulShutdown",
                137: "ForcedShutdown",
                2: "Interrupt",
            }.get(return_code, "GracefulShutdown")

            track_event(
                "cli_run_shutdown",
                {
                    "success": True,  # Not an error
                    "shutdown_type": shutdown_type,
                    "exit_code": return_code,
                },
            )
        else:
            # Actual errors (unexpected exit codes)
            track_event(
                "cli_run_failed",
                {
                    "success": False,
                    "error_type": "UnexpectedExit",
                    "error_message": (f"Server process exited unexpectedly with code {return_code}"),
                    "exit_code": return_code,
                    "operation": "server_process_execution",
                    "context": "Server process terminated with unexpected exit code",
                },
            )

        # Exit with the same code as the server
        if return_code != 0:
            raise typer.Exit(code=return_code)
    except Exception as e:
        track_detailed_error(
            "cli_run_failed",
            e,
            context="Server execution or startup failure",
            operation="run_server_execution",
            additional_props={"has_dist_dir": dist_dir.exists() if dist_dir else False},
        )
        raise


# Add telemetry command group
@app.command()
def telemetry(
    action: str = typer.Argument(..., help="Action to perform: 'enable' or 'disable'"),
) -> None:
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
    create_welcome_banner(__version__, console)

    # Add telemetry notice if enabled
    if is_telemetry_enabled():
        console.print(
            "[dim]📊 Anonymous usage data is collected to improve Golf. Disable with: golf telemetry disable[/dim]\n"
        )

    # Run the CLI app
    app()
