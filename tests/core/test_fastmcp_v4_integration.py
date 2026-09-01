"""Real FastMCP 4 client integration tests for generated Golf servers."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastmcp import Client

from golf.core.builder import build_project
from golf.core.config import load_settings


def _write_project(project: Path) -> None:
    project.mkdir()
    (project / "tools").mkdir()
    (project / "resources").mkdir()
    (project / "prompts").mkdir()
    (project / "golf.json").write_text(json.dumps({"name": "v4-integration", "transport": "streamable-http"}))
    (project / "tools" / "annotated.py").write_text(
        '''
annotations = {"readOnlyHint": True, "idempotentHint": True}

async def run(name: str = "World") -> str:
    """Return a greeting."""
    return f"Hello, {name}!"

export = run
'''
    )
    (project / "resources" / "status.py").write_text(
        '''
resource_uri = "status://server"

async def read() -> str:
    """Read server status."""
    return "ready"

export = read
'''
    )
    (project / "resources" / "user.py").write_text(
        '''
resource_uri = "user://{user_id}"

async def read(user_id: str) -> str:
    """Read a user."""
    return f"user:{user_id}"

export = read
'''
    )
    (project / "prompts" / "welcome.py").write_text(
        '''
async def render(name: str) -> list[str]:
    """Render a welcome prompt."""
    return [f"Welcome {name}"]

export = render
'''
    )
    (project / "middleware.py").write_text(
        """
from fastmcp.server.middleware import Middleware

seen = []

class RecordingMiddleware(Middleware):
    async def on_message(self, context, call_next):
        seen.append((context.type, context.method))
        return await call_next(context)
"""
    )


def _load_server(build_dir: Path, module_name: str) -> ModuleType:
    server_path = build_dir / "server.py"
    for name in [
        key for key in sys.modules if key == "middleware" or key == "components" or key.startswith("components.")
    ]:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(module_name, server_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(build_dir))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(build_dir))
    return module


@pytest.mark.parametrize(
    ("mode", "expected_protocol"),
    [("auto", "2026-07-28"), ("legacy", None)],
)
async def test_generated_server_public_apis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, expected_protocol: str | None
) -> None:
    monkeypatch.setenv("FASTMCP_MCP_CAMELCASE_COMPAT", "false")
    project = tmp_path / f"project-{mode}"
    build_dir = tmp_path / f"build-{mode}"
    _write_project(project)
    build_project(project, load_settings(project), build_dir)
    server = _load_server(build_dir, f"generated_server_{mode}")

    async with Client(server.mcp, mode=mode) as client:
        if expected_protocol is None:
            assert client.protocol_version != "2026-07-28"
        else:
            assert client.protocol_version == expected_protocol

        tools = await client.list_tools()
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        prompts = await client.list_prompts()

        tool = next(item for item in tools if item.name == "annotated")
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert (await client.call_tool("annotated", {"name": "Golf"})).data == "Hello, Golf!"
        assert (await client.read_resource("status://server"))[0].text == "ready"
        assert (await client.read_resource("user://42"))[0].text == "user:42"
        prompt = await client.get_prompt("welcome", {"name": "Golf"})
        assert prompt.messages[0].content.text == "Welcome Golf"
        assert any(item.uri_template == "user://{user_id}" for item in templates)
        assert {item.uri for item in resources} == {"status://server"}
        assert {item.name for item in prompts} == {"welcome"}

    middleware = sys.modules["middleware"]
    assert ("request", "tools/call") in middleware.seen
    assert all(message_type in {"request", "notification"} for message_type, _ in middleware.seen)
    methods = {method for _, method in middleware.seen}
    if mode == "auto":
        assert "server/discover" in methods
        assert "initialize" not in methods
    else:
        assert "initialize" in methods


def _write_input_project(project: Path) -> None:
    project.mkdir()
    (project / "tools").mkdir()
    (project / "resources").mkdir()
    (project / "prompts").mkdir()
    (project / "golf.json").write_text(json.dumps({"name": "v4-input"}))
    (project / "tools" / "ask.py").write_text(
        '''
from mcp_types import InputRequiredResult
from golf.utilities import elicit

async def run() -> str | InputRequiredResult:
    """Ask the user for confirmation."""
    answer = await elicit("Continue?", bool)
    if isinstance(answer, InputRequiredResult):
        return answer
    return "yes" if answer else "no"

export = run
'''
    )
    (project / "tools" / "sample.py").write_text(
        '''
from mcp_types import InputRequiredResult
from golf.utilities import sample

async def run(topic: str) -> str | InputRequiredResult:
    """Ask the client language model to explain a topic."""
    answer = await sample(f"Explain {topic}", max_tokens=20)
    if isinstance(answer, InputRequiredResult):
        return answer
    return answer

export = run
'''
    )


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_elicitation_and_sampling_across_protocol_eras(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setenv("FASTMCP_MCP_CAMELCASE_COMPAT", "false")
    project = tmp_path / f"input-{mode}"
    build_dir = tmp_path / f"input-build-{mode}"
    _write_input_project(project)
    build_project(project, load_settings(project), build_dir)
    server = _load_server(build_dir, f"input_server_{mode}")

    async def elicit_handler(message, response_type, params, context):
        assert message == "Continue?"
        return True

    async def sampling_handler(messages, params, context):
        assert messages[0].content.text == "Explain Golf"
        return "Golf is a framework."

    async with Client(
        server.mcp,
        mode=mode,
        elicitation_handler=elicit_handler,
        sampling_handler=sampling_handler,
    ) as client:
        assert (await client.call_tool("ask")).data == "yes"
        assert (await client.call_tool("sample", {"topic": "Golf"})).data == "Golf is a framework."
