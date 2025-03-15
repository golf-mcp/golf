# Authed Integration with Model Context Protocol (MCP)

This integration provides authentication and identity management for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) using Authed.

## Overview

The Model Context Protocol (MCP) is an open protocol that enables seamless integration between LLM applications and external data sources and tools. Authed is an identity and authentication system built specifically for AI agents. This integration allows Authed to serve as the authentication layer for MCP servers and clients.

## Features

- **Secure Authentication**: Use Authed's cryptographic signatures to verify agent identities
- **Permission Management**: Control which agents can access which MCP servers
- **Token-based Access**: Generate and verify interaction tokens for secure communication
- **Adapter Pattern**: Non-invasive integration that works with existing MCP implementations

## Installation

```bash
# Install Authed
pip install authed
```

## Usage

### Server Integration

To integrate Authed with your MCP server:

```python
from client.sdk import Authed
from integrations.mcp import AuthedMCPServerAdapter

# Initialize Authed
authed = Authed.from_env()

# Create adapter
adapter = AuthedMCPServerAdapter(authed)

# Process authenticated requests
async def handle_request(request_data, headers):
    request = json.loads(request_data)
    response = await adapter.process_mcp_request(
        your_mcp_handler,  # Your existing MCP request handler
        request,
        headers
    )
    return json.dumps(response)
```

### Client Integration

To integrate Authed with your MCP client:

```python
from client.sdk import Authed
from integrations.mcp import AuthedMCPClientAdapter

# Initialize Authed
authed = Authed.from_env()

# Create adapter
adapter = AuthedMCPClientAdapter(authed)

# Make authenticated requests
async def send_request(request, server_agent_id):
    # Prepare request with authentication
    prepared = await adapter.prepare_request(
        request=request,
        target_server_id=server_agent_id
    )
    
    # Send request using your existing MCP client
    return await your_mcp_client.send_request(
        request=prepared["request"],
        headers=prepared["headers"]
    )
```

### Server Registration

Register an MCP server as an agent in Authed:

```python
from integrations.mcp import register_mcp_server

# Register server
server_info = await register_mcp_server(
    authed=authed,
    name="My MCP Server",
    description="An MCP server with Authed authentication",
    capabilities={"resources": True, "tools": True}
)

# Save server credentials
agent_id = server_info["agent_id"]
private_key = server_info["private_key"]
public_key = server_info["public_key"]
```

### Permission Management

Grant access from one agent to an MCP server:

```python
from integrations.mcp import grant_mcp_access

# Grant access
success = await grant_mcp_access(
    authed=authed,
    client_agent_id="client-agent-id",
    server_agent_id="server-agent-id",
    permissions=["read", "execute"]  # Optional custom permissions
)
```

## Examples

This integration includes two example implementations:

- `server_example.py`: A simple MCP server with Authed authentication
- `client_example.py`: A simple MCP client that makes authenticated requests to an MCP server

To run the examples:

1. Set up Authed environment variables:
   ```bash
   export AUTHED_REGISTRY_URL="https://api.getauthed.dev"
   export AUTHED_AGENT_ID="your-agent-id"
   export AUTHED_AGENT_SECRET="your-agent-secret"
   export AUTHED_PRIVATE_KEY="your-private-key"
   export AUTHED_PUBLIC_KEY="your-public-key"
   ```

2. Run the server example:
   ```bash
   python -m integrations.mcp.server_example
   ```

3. Run the client example:
   ```bash
   python -m integrations.mcp.client_example
   ```

## Security Considerations

- Always use HTTPS for production deployments
- Implement token expiration and refresh mechanisms
- Validate all cryptographic signatures
- Maintain audit logs of authentication events
- Implement rate limiting to prevent abuse

## License

This integration is licensed under the MIT License. 