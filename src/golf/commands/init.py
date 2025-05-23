"""Project initialization command implementation."""

import os
import shutil
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from golf.core.telemetry import track_event

console = Console()


def initialize_project(
    project_name: str,
    output_dir: Path,
    template: str = "basic",
) -> None:
    """Initialize a new GolfMCP project with the specified template.
    
    Args:
        project_name: Name of the project
        output_dir: Directory where the project will be created
        template: Template to use (basic or api_key)
    """
    # Validate template
    valid_templates = ("basic", "api_key")
    if template not in valid_templates:
        console.print(f"[bold red]Error:[/bold red] Unknown template '{template}'")
        console.print(f"Available templates: {', '.join(valid_templates)}")
        track_event("cli_init_failed", {"success": False})
        return
    
    # Check if directory exists
    if output_dir.exists():
        if not output_dir.is_dir():
            console.print(
                f"[bold red]Error:[/bold red] '{output_dir}' exists but is not a directory."
            )
            track_event("cli_init_failed", {"success": False})
            return
        
        # Check if directory is empty
        if any(output_dir.iterdir()):
            if not Confirm.ask(
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
        console.print(
            f"[bold red]Error:[/bold red] Could not find template '{template}'"
        )
        track_event("cli_init_failed", {"success": False})
        return
    
    # Copy template files
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold green]Creating project structure...[/bold green]"),
        transient=True,
    ) as progress:
        progress.add_task("copying", total=None)
        
        # Copy directory structure
        _copy_template(template_dir, output_dir, project_name)
    
    # Create virtual environment
    console.print("[bold green]Project initialized successfully![/bold green]")
    console.print(f"\nTo get started, run:")
    console.print(f"  cd {output_dir.name}")
    console.print(f"  golf build dev")
    
    # Track successful initialization
    track_event("cli_init_success", {
        "success": True,
        "template": template
    })


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
            with open(source_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Replace template variables
            content = content.replace("{{project_name}}", project_name)
            content = content.replace("{{project_name_lowercase}}", project_name.lower())
            
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            # Binary file, just copy
            shutil.copy2(source_path, target_path)
    
    # Create .env file
    env_file = target_dir / ".env"
    with open(env_file, "w", encoding="utf-8") as f:
        f.write(f"GOLF_NAME={project_name}\n")
        f.write("GOLF_HOST=127.0.0.1\n")
        f.write("GOLF_PORT=3000\n")
    
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


def _is_text_file(path: Path) -> bool:
    """Check if a file is a text file that needs variable substitution.
    
    Args:
        path: Path to check
        
    Returns:
        True if the file is a text file
    """
    # List of known text file extensions
    text_extensions = {
        ".py", ".md", ".txt", ".html", ".css", ".js", ".json", 
        ".yml", ".yaml", ".toml", ".ini", ".cfg", ".env", ".example"
    }
    
    # Check if the file has a text extension
    if path.suffix in text_extensions:
        return True
    
    # Check specific filenames without extensions
    if path.name in {".gitignore", "README", "LICENSE"}:
        return True
    
    # Try to detect if it's a text file by reading a bit of it
    try:
        with open(path, "r", encoding="utf-8") as f:
            f.read(1024)
        return True
    except UnicodeDecodeError:
        return False 