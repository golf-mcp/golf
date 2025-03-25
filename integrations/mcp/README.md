# Authed MCP Integration

This package provides integration between [Authed](https://getauthed.dev) authentication and the [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol).

## Overview

The Authed MCP integration allows you to:

1. Create MCP servers with Authed authentication
2. Create MCP clients that can authenticate with Authed


## Installation

```bash
pip install authed-mcp
```

## Quick Start

### Server Setup

```python
from authed import Authed
from mcp.server.fastmcp import FastMCP
from authed_mcp import AuthedMiddleware
from starlette.applications import Starlette

# Initialize Authed SDK
authed = Authed.initialize(
    registry_url=os.getenv("AUTHED_REGISTRY_URL"),
    agent_id=os.getenv("AUTHED_AGENT_ID"),
    agent_secret=os.getenv("AUTHED_AGENT_SECRET"),
    private_key=os.getenv("AUTHED_PRIVATE_KEY"),
    public_key=os.getenv("AUTHED_PUBLIC_KEY")
)

# Create MCP server with Authed protection
app = Starlette(
    middleware=[
        Middleware(
            AuthedMiddleware,
            authed=authed,
            require_auth=True
        )
    ]
)
```

### Client Setup

```python
from authed.sdk import Authed
from mcp import ClientSession
from authed_mcp import get_auth_headers

# Initialize client
authed = Authed.initialize(
    registry_url=os.getenv("AUTHED_REGISTRY_URL"),
    agent_id=os.getenv("AUTHED_AGENT_ID"),
    agent_secret=os.getenv("AUTHED_AGENT_SECRET"),
    private_key=os.getenv("AUTHED_PRIVATE_KEY"),
    public_key=os.getenv("AUTHED_PUBLIC_KEY")
)

# Connect with authentication
headers = await get_auth_headers(
    authed=authed,
    url="http://localhost:8000/sse",
    method="GET",
    target_agent_id=os.getenv("TARGET_AGENT_ID")
)
```

## Environment Setup

Required environment variables:

```bash
# For both client and server
AUTHED_REGISTRY_URL=https://api.getauthed.dev
AUTHED_AGENT_ID=your_agent_id
AUTHED_AGENT_SECRET=your_agent_secret

# Additional for client
TARGET_AGENT_ID=server_agent_id  # The agent ID of the server you're connecting to
```

## Examples

Check out the `examples` directory for complete working examples:

- `examples/server/` - Example MCP server with Authed authentication
- `examples/client/` - Example MCP client that connects to the server

## Security Considerations

1. Always use HTTPS in production
2. Keep your agent secrets secure
3. Never use the same agent ID for both client and server
4. Ensure proper DPoP token validation

## Contributing

Contributions are welcome! Please check out our [Contributing Guide](CONTRIBUTING.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
