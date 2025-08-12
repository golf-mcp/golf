"""Pytest configuration and shared fixtures for Golf MCP tests."""

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test isolation."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_project(temp_dir: Path) -> Path:
    """Create a minimal Golf project structure for testing."""
    project_dir = temp_dir / "test_project"
    project_dir.mkdir()

    # Create golf.json
    golf_json = project_dir / "golf.json"
    golf_json.write_text(
        """{
    "name": "TestProject",
    "description": "A test Golf project",
    "host": "localhost",
    "port": 3000,
    "transport": "sse"
}"""
    )

    # Create component directories
    (project_dir / "tools").mkdir()
    (project_dir / "resources").mkdir()
    (project_dir / "prompts").mkdir()

    return project_dir


@pytest.fixture
def sample_tool_file(sample_project: Path) -> Path:
    """Create a sample tool file."""
    tool_file = sample_project / "tools" / "hello.py"
    tool_file.write_text(
        '''"""A simple hello tool."""

from typing import Annotated
from pydantic import BaseModel, Field


class Output(BaseModel):
    """Response from the hello tool."""
    message: str


async def hello(
    name: Annotated[str, Field(description="Name to greet")] = "World"
) -> Output:
    """Say hello to someone."""
    return Output(message=f"Hello, {name}!")


export = hello
'''
    )
    return tool_file


@pytest.fixture(autouse=True)
def isolate_telemetry(monkeypatch) -> None:
    """Isolate telemetry for tests to prevent actual tracking."""
    monkeypatch.setenv("GOLF_TELEMETRY", "0")
    # Also prevent any file system telemetry operations
    monkeypatch.setenv("HOME", str(Path(tempfile.mkdtemp())))
