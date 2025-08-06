"""Build command for GolfMCP.

This module implements the `golf build` command which generates a standalone
FastMCP application from a GolfMCP project.
"""

import argparse
from pathlib import Path

from rich.console import Console

from golf.core.builder import build_project as core_build_project
from golf.core.config import Settings, load_settings

console = Console()


def build_project(
    project_path: Path,
    settings: Settings,
    output_dir: Path,
    build_env: str = "prod",
    copy_env: bool = False,
) -> None:
    """Build a standalone FastMCP application from a GolfMCP project.

    Args:
        project_path: Path to the project root
        settings: Project settings
        output_dir: Directory to output the built project
        build_env: Build environment ('dev' or 'prod')
        copy_env: Whether to copy environment variables to the built app
    """
    # Call the centralized build function from core.builder
    core_build_project(project_path, settings, output_dir, build_env=build_env, copy_env=copy_env)


# Add a main section to run the build_project function when this module is
# executed directly
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a standalone FastMCP application")
    parser.add_argument(
        "--project-path",
        "-p",
        type=Path,
        default=Path.cwd(),
        help="Path to the project root (default: current directory)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path.cwd() / "dist",
        help="Directory to output the built project (default: ./dist)",
    )
    parser.add_argument(
        "--build-env",
        type=str,
        default="prod",
        choices=["dev", "prod"],
        help="Build environment to use (default: prod)",
    )
    parser.add_argument(
        "--copy-env",
        action="store_true",
        help="Copy environment variables to the built application",
    )

    args = parser.parse_args()

    # Load settings from the project path
    settings = load_settings(args.project_path)

    # Execute the build
    build_project(
        args.project_path,
        settings,
        args.output_dir,
        build_env=args.build_env,
        copy_env=args.copy_env,
    )
