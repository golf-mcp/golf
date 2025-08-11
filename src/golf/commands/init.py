"""Project initialization command implementation."""

import shutil
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from golf.cli.branding import (
    create_success_message,
    create_info_panel,
    STATUS_ICONS,
    GOLF_ORANGE,
)

from golf.core.telemetry import (
    track_command,
    track_event,
    set_telemetry_enabled,
    load_telemetry_preference,
)

console = Console()


def initialize_project(
    project_name: str,
    output_dir: Path,
) -> None:
    """Initialize a new GolfMCP project.

    Args:
        project_name: Name of the project
        output_dir: Directory where the project will be created
    """
    try:
        # Use the basic template by default
        template = "basic"

        # Check if directory exists
        if output_dir.exists():
            if not output_dir.is_dir():
                console.print(f"[bold red]Error:[/bold red] '{output_dir}' exists but is not a directory.")
                track_command(
                    "init",
                    success=False,
                    error_type="NotADirectory",
                    error_message="Target exists but is not a directory",
                )
                return

            # Check if directory is empty
            if any(output_dir.iterdir()) and not Confirm.ask(
                f"Directory '{output_dir}' is not empty. Continue anyway?",
                default=False,
            ):
                console.print("Initialization cancelled.")
                track_event("cli_init_cancelled", {"success": False})
                return
        else:
            # Create the directory
            output_dir.mkdir(parents=True)

        # Find template directory within the installed package
        import golf

        package_init_file = Path(golf.__file__)
        # The 'examples' directory is now inside the 'golf' package directory
        # e.g. golf/examples/basic, so go up one from __init__.py to get to 'golf'
        template_dir = package_init_file.parent / "examples" / template

        if not template_dir.exists():
            console.print(f"[bold red]Error:[/bold red] Could not find template '{template}'")
            track_command(
                "init",
                success=False,
                error_type="TemplateNotFound",
                error_message=f"Template directory not found: {template}",
            )
            return

        # Copy template files
        with Progress(
            SpinnerColumn(),
            TextColumn(
                f"[bold {GOLF_ORANGE}]{STATUS_ICONS['building']} Creating project structure...[/bold {GOLF_ORANGE}]"
            ),
            transient=True,
        ) as progress:
            progress.add_task("copying", total=None)

            # Copy directory structure
            _copy_template(template_dir, output_dir, project_name)

        # Ask for telemetry consent
        _prompt_for_telemetry_consent()

        # Show success message
        console.print()
        create_success_message("Project initialized successfully!", console)

        # Show next steps
        next_steps = f"cd {output_dir.name}\ngolf build dev\ngolf run"
        create_info_panel("Next Steps", next_steps, console)

        # Track successful initialization
        track_event("cli_init_success", {"success": True, "template": template})
    except Exception as e:
        # Capture error details for telemetry
        error_type = type(e).__name__
        error_message = str(e)

        console.print(f"[bold red]Error during initialization:[/bold red] {error_message}")
        track_command("init", success=False, error_type=error_type, error_message=error_message)

        # Re-raise to maintain existing behavior
        raise


def _copy_template(source_dir: Path, target_dir: Path, project_name: str) -> None:
    """Copy template files to the target directory, with variable substitution.

    Args:
        source_dir: Source template directory
        target_dir: Target project directory
        project_name: Name of the project (for substitutions)
    """
    # Create standard directory structure
    (target_dir / "tools").mkdir(exist_ok=True)
    (target_dir / "resources").mkdir(exist_ok=True)
    (target_dir / "prompts").mkdir(exist_ok=True)

    # Copy all files from the template
    for source_path in source_dir.glob("**/*"):
        # Skip if directory (we'll create directories as needed)
        if source_path.is_dir():
            continue

        # Compute relative path
        rel_path = source_path.relative_to(source_dir)
        target_path = target_dir / rel_path

        # Create parent directories if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy and substitute content for text files
        if _is_text_file(source_path):
            with open(source_path, encoding="utf-8") as f:
                content = f.read()

            # Replace template variables
            content = content.replace("{{project_name}}", project_name)
            content = content.replace("{{project_name_lowercase}}", project_name.lower())

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            # Binary file, just copy
            shutil.copy2(source_path, target_path)

    # Create a .gitignore if it doesn't exist
    gitignore_file = target_dir / ".gitignore"
    if not gitignore_file.exists():
        with open(gitignore_file, "w", encoding="utf-8") as f:
            f.write("# Python\n")
            f.write("__pycache__/\n")
            f.write("*.py[cod]\n")
            f.write("*$py.class\n")
            f.write("*.so\n")
            f.write(".Python\n")
            f.write("env/\n")
            f.write("build/\n")
            f.write("develop-eggs/\n")
            f.write("dist/\n")
            f.write("downloads/\n")
            f.write("eggs/\n")
            f.write(".eggs/\n")
            f.write("lib/\n")
            f.write("lib64/\n")
            f.write("parts/\n")
            f.write("sdist/\n")
            f.write("var/\n")
            f.write("*.egg-info/\n")
            f.write(".installed.cfg\n")
            f.write("*.egg\n\n")
            f.write("# Environment\n")
            f.write(".env\n")
            f.write(".venv\n")
            f.write("env/\n")
            f.write("venv/\n")
            f.write("ENV/\n")
            f.write("env.bak/\n")
            f.write("venv.bak/\n\n")
            f.write("# GolfMCP\n")
            f.write(".golf/\n")
            f.write("dist/\n")


def _prompt_for_telemetry_consent() -> None:
    """Prompt user for telemetry consent and save their preference."""
    import os

    # Skip prompt in test mode, when telemetry is explicitly disabled, or if
    # preference already exists
    if os.environ.get("GOLF_TEST_MODE", "").lower() in ("1", "true", "yes", "on"):
        return

    # Skip if telemetry is explicitly disabled in environment
    if os.environ.get("GOLF_TELEMETRY", "").lower() in ("0", "false", "no", "off"):
        return

    # Check if user already has a saved preference
    existing_preference = load_telemetry_preference()
    if existing_preference is not None:
        return  # User already made a choice

    console.print()
    console.rule("[bold blue]Anonymous usage analytics[/bold blue]", style="blue")
    console.print()
    console.print("Golf can collect [bold]anonymous usage analytics[/bold] to help improve the tool.")
    console.print()
    console.print("[dim]What we collect:[/dim]")
    console.print("  • Command usage (init, build, run)")
    console.print("  • Error types (to fix bugs)")
    console.print("  • Golf version and Python version")
    console.print("  • Operating system type")
    console.print()
    console.print("[dim]What we DON'T collect:[/dim]")
    console.print("  • Your code or project content")
    console.print("  • File paths or project names")
    console.print("  • Personal information")
    console.print("  • IP addresses")
    console.print()
    console.print("You can change this anytime by setting GOLF_TELEMETRY=0 in your environment.")
    console.print()

    enable_telemetry = Confirm.ask("[bold]Enable anonymous usage analytics?[/bold]", default=False)

    set_telemetry_enabled(enable_telemetry, persist=True)

    if enable_telemetry:
        console.print("[green]✓[/green] Anonymous analytics enabled")
    else:
        console.print("[yellow]○[/yellow] Anonymous analytics disabled")
    console.print()


def _is_text_file(path: Path) -> bool:
    """Check if a file is a text file that needs variable substitution.

    Args:
        path: Path to check

    Returns:
        True if the file is a text file
    """
    # List of known text file extensions
    text_extensions = {
        ".py",
        ".md",
        ".txt",
        ".html",
        ".css",
        ".js",
        ".json",
        ".yml",
        ".yaml",
        ".toml",
        ".ini",
        ".cfg",
        ".env",
        ".example",
    }

    # Check if the file has a text extension
    if path.suffix in text_extensions:
        return True

    # Check specific filenames without extensions
    if path.name in {".gitignore", "README", "LICENSE"}:
        return True

    # Try to detect if it's a text file by reading a bit of it
    try:
        with open(path, encoding="utf-8") as f:
            f.read(1024)
        return True
    except UnicodeDecodeError:
        return False
