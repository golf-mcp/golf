<div align="center">
  <img src="./golf-banner.png" alt="Golf Banner">
  
  <h1>Golf</h1>
  
  <p><strong>Easiest framework for building MCP servers.</strong></p>
  
  <p>
    <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
    <a href="https://github.com/golf-mcp/golf/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs"></a>
    <a href="https://github.com/golf-mcp/golf/issues"><img src="https://img.shields.io/badge/support-contact%20author-purple.svg" alt="Support"></a>
  </p>
  
  <p><a href="https://docs.golf.dev">Docs</a></p>
</div>

## Overview

Golf is a **framework** designed to streamline the creation of MCP server applications. It allows developers to define server's capabilities—*tools*, *prompts*, and *resources*—as simple Python files within a conventional directory structure. Golf then automatically discovers, parses, and compiles these components into a runnable FastMCP server, minimizing boilerplate and accelerating development.

With Golf, you can focus on implementing your agent's logic rather than wrestling with server setup and integration complexities. It's built for developers who want a quick, organized way to build powerful MCP servers.

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
This will start the FastMCP server, typically on `http://127.0.0.1:3000` (configurable in `golf.json`).

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
└─ pre_build.py       # (Optional) Script for pre-build hooks (e.g., auth setup)
```

-   **`golf.json`**: Configures server name, port, transport, telemetry, and other build settings.
-   **`tools/`**, **`resources/`**, **`prompts/`**: Contain your Python files, each defining a single component. These directories can also contain nested subdirectories to further organize your components (e.g., `tools/payments/charge.py`). The module docstring of each file serves as the component's description.
    -   Component IDs are automatically derived from their file path. For example, `tools/hello.py` becomes `hello`, and a nested file like `tools/payments/submit.py` would become `submit-payments` (filename, followed by reversed parent directories under the main category, joined by hyphens).
-   **`common.py`** (not shown, but can be placed in subdirectories like `tools/payments/common.py`): Used to share code (clients, models, etc.) among components in the same subdirectory.

## Example: Defining a Tool

Creating a new tool is as simple as adding a Python file to the `tools/` directory. The example `tools/hello.py` in the boilerplate looks like this:

```python
# tools/hello.py
"""Hello World tool {{project_name}}."""

from pydantic import BaseModel

class Output(BaseModel):
    """Response from the hello tool."""
    message: str

async def hello(
    name: str = "World",
    greeting: str = "Hello"
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

## Configuration (`golf.json`)

Key aspects of your Golf server are configured in `golf.json`. The boilerplate provides a starting point like this:

```jsonc
{
  "name": "{{project_name}}",          // Will be replaced with your project name
  "description": "A Golf project", // A default description
  "host": "127.0.0.1",               // Server host address
  "port": 3000,                      // Server port
  "transport": "sse",                // 'sse', 'streamable-http', or 'stdio'
  "opentelemetry_enabled": false,    // OpenTelemetry disabled by default - we're working on this as a feature
  "opentelemetry_default_exporter": "console"
}
```
## Roadmap

Here are the things we are working hard on:

*   **Native OpenTelemetry implementation for tracing**
*   **`golf deploy` command for one click deployments to Vercel, Blaxel and other providers**
*   **Production-ready OAuth token management, to allow for persistent, encrypted token storage and client mapping**

## Documentation

For more information, please visit our official documentation:

[https://docs.golf.dev](https://docs.golf.dev)

<div align="center">
Made with ❤️ in Warsaw, Poland and SF
</div>