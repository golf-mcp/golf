<div align="center">
  <img src="./golf-banner.png" alt="Golf Banner">
  
  <br>
  
  <h1 align="center">
    <br>
    <span style="font-size: 80px;">⛳ Golf</span>
    <br>
  </h1>
  
  <h3 align="center">
    Easiest framework for building MCP servers
  </h3>
  
  <br>
  
  <p>
    <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
    <a href="https://github.com/golf-mcp/golf/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs"></a>
    <a href="https://github.com/golf-mcp/golf/issues"><img src="https://img.shields.io/badge/support-contact%20author-purple.svg" alt="Support"></a>
  </p>
  
  <p>
    <a href="https://docs.golf.dev"><strong>📚 Documentation</strong></a>
  </p>
</div>

## Overview

Golf is a **framework** designed to streamline the creation of MCP server applications. It allows developers to define server's capabilities—*tools*, *prompts*, and *resources*—as simple Python files within a conventional directory structure. Golf then automatically discovers, parses, and compiles these components into a runnable MCP server, minimizing boilerplate and accelerating development.

With Golf v0.2.0, you get **enterprise-grade authentication** (JWT, OAuth Server, API key, development tokens), **built-in utilities** for LLM interactions, and **automatic telemetry** integration. Focus on implementing your agent's logic while Golf handles authentication, monitoring, and server infrastructure.

## Quick Start

Get your Golf project up and running in a few simple steps:

### 1. Install Golf

Ensure you have Python (3.10+ recommended) installed. Then, install Golf using pip:

```bash
pip install golf-mcp
```

### 2. Initialize Your Project

Use the Golf CLI to scaffold a new project:

```bash
golf init your-project-name
```
This command creates a new directory (`your-project-name`) with a basic project structure, including example tools, resources, and a `golf.json` configuration file.

### 3. Run the Development Server

Navigate into your new project directory and start the development server:

```bash
cd your-project-name
golf build dev
golf run
```
This will start the MCP server, typically on `http://localhost:3000` (configurable in `golf.json`).

That's it! Your Golf server is running and ready for integration.

## Basic Project Structure

A Golf project initialized with `golf init` will have a structure similar to this:

```
<your-project-name>/
│
├─ golf.json          # Main project configuration
│
├─ tools/             # Directory for tool implementations
│   └─ hello.py       # Example tool
│
├─ resources/         # Directory for resource implementations
│   └─ info.py        # Example resource
│
├─ prompts/           # Directory for prompt templates
│   └─ welcome.py     # Example prompt
│
├─ .env               # Environment variables (e.g., API keys, server port)
└─ auth.py            # Authentication configuration (JWT, OAuth Server, API key, dev tokens)
```

-   **`golf.json`**: Configures server name, port, transport, telemetry, and other build settings.
-   **`auth.py`**: Dedicated authentication configuration file (new in v0.2.0, breaking change from v0.1.x authentication API) for JWT, OAuth Server, API key, or development authentication.
-   **`tools/`**, **`resources/`**, **`prompts/`**: Contain your Python files, each defining a single component. These directories can also contain nested subdirectories to further organize your components (e.g., `tools/payments/charge.py`). The module docstring of each file serves as the component's description.
    -   Component IDs are automatically derived from their file path. For example, `tools/hello.py` becomes `hello`, and a nested file like `tools/payments/submit.py` would become `submit_payments` (filename, followed by reversed parent directories under the main category, joined by underscores).
-   **`common.py`** (not shown, but can be placed in subdirectories like `tools/payments/common.py`): Used to share code (clients, models, etc.) among components in the same subdirectory.

## Example: Defining a Tool

Creating a new tool is as simple as adding a Python file to the `tools/` directory. The example `tools/hello.py` in the boilerplate looks like this:

```python
# tools/hello.py
"""Hello World tool {{project_name}}."""

from typing import Annotated
from pydantic import BaseModel, Field

class Output(BaseModel):
    """Response from the hello tool."""
    message: str

async def hello(
    name: Annotated[str, Field(description="The name of the person to greet")] = "World",
    greeting: Annotated[str, Field(description="The greeting phrase to use")] = "Hello"
) -> Output:
    """Say hello to the given name.
    
    This is a simple example tool that demonstrates the basic structure
    of a tool implementation in Golf.
    """
    print(f"{greeting} {name}...")
    return Output(message=f"{greeting}, {name}!")

# Designate the entry point function
export = hello
```
Golf will automatically discover this file. The module docstring `"""Hello World tool {{project_name}}."""` is used as the tool's description. It infers parameters from the `hello` function's signature and uses the `Output` Pydantic model for the output schema. The tool will be registered with the ID `hello`.

## Authentication & Features

Golf includes enterprise-grade authentication, built-in utilities, and automatic telemetry:

```python
# auth.py - Configure authentication
from golf.auth import configure_auth, JWTAuthConfig, StaticTokenConfig, OAuthServerConfig

# JWT authentication (production)
configure_auth(JWTAuthConfig(
    jwks_uri_env_var="JWKS_URI",
    issuer_env_var="JWT_ISSUER", 
    audience_env_var="JWT_AUDIENCE",
    required_scopes=["read", "write"]
))

# OAuth Server mode (Golf acts as OAuth 2.0 server)
# configure_auth(OAuthServerConfig(
#     base_url="https://your-golf-server.com",
#     valid_scopes=["read", "write", "admin"]
# ))

# Static tokens (development only)
# configure_auth(StaticTokenConfig(
#     tokens={"dev-token": {"client_id": "dev", "scopes": ["read"]}}
# ))

# Built-in utilities available in all tools
from golf.utils import elicit, sample, get_context
```

```bash
# Automatic telemetry with Golf Platform
export GOLF_API_KEY="your-key"
golf run  # ✅ Telemetry enabled automatically
```

**[📚 Complete Documentation →](https://docs.golf.dev)**

## Configuration

Basic configuration in `golf.json`:

```json
{
  "name": "My Golf Server",
  "host": "localhost",
  "port": 3000,
  "transport": "sse",
  "opentelemetry_enabled": false,
  "detailed_tracing": false
}
```

- **`transport`**: Choose `"sse"`, `"streamable-http"`, or `"stdio"`
- **`opentelemetry_enabled`**: Auto-enabled with `GOLF_API_KEY`
- **`detailed_tracing`**: Capture input/output (use carefully with sensitive data)


## Privacy & Telemetry

Golf collects **anonymous** usage data on the CLI to help us understand how the framework is being used and improve it over time. The data collected includes:

- Commands run (init, build, run)
- Success/failure status (no error details)
- Golf version, Python version (major.minor only), and OS type
- Template name (for init command only)
- Build environment (dev/prod for build commands only)

**No personal information, project names, code content, or error messages are ever collected.**

### Opting Out

You can disable telemetry in several ways:

1. **Using the telemetry command** (recommended):
   ```bash
   golf telemetry disable
   ```
   This saves your preference permanently. To re-enable:
   ```bash
   golf telemetry enable
   ```

2. **During any command**: Add `--no-telemetry` to save your preference:
   ```bash
   golf init my-project --no-telemetry
   ```

Your telemetry preference is stored in `~/.golf/telemetry.json` and persists across all Golf commands.

<div align="center">
Made with ❤️ in Warsaw, Poland and SF
</div>