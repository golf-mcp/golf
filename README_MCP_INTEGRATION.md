# Authed Integration with Model Context Protocol (MCP)

This project demonstrates how to integrate [Authed](https://getauthed.dev) with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) to provide secure authentication for AI agents accessing MCP servers.

## Overview

The Model Context Protocol (MCP) is an open protocol that enables seamless integration between LLM applications and external data sources and tools. Authed is an identity and authentication system built specifically for AI agents. This integration allows Authed to serve as the authentication layer for MCP servers and clients.

## Features

- **Secure Authentication**: Use Authed's cryptographic signatures to verify agent identities
- **Permission Management**: Control which agents can access which MCP servers
- **Token-based Access**: Generate and verify interaction tokens for secure communication
- **Adapter Pattern**: Non-invasive integration that works with existing MCP implementations

## Files

- `integration_plan.md`: Detailed plan for integrating Authed with MCP
- `mcp_authed_adapter.py`: Core adapter implementation for MCP servers and clients
- `mcp_server_example.py`: Example MCP server with Authed authentication
- `mcp_client_example.py`: Example MCP client with Authed authentication

## Prerequisites

- Python 3.8+
- Authed SDK (`pip install authed`)
- Environment variables set up for Authed (see below)

## Setup

1. **Install dependencies**:
   ```bash
   pip install authed
   ```

2. **Set up Authed environment variables**:
   ```bash
   # Registry and agent configuration
   export AUTHED_REGISTRY_URL="https://api.getauthed.dev"
   export AUTHED_AGENT_ID="your-agent-id"
   export AUTHED_AGENT_SECRET="your-agent-secret"

   # Keys for signing and verifying requests
   export AUTHED_PRIVATE_KEY="your-private-key"
   export AUTHED_PUBLIC_KEY="your-public-key"
   ```

3. **Run the server example** to register an MCP server with Authed:
   ```bash
   python mcp_server_example.py
   ```
   This will create a `.env.mcp_server` file with the server's credentials.

4. **Run the client example** to demonstrate authenticated requests:
   ```bash
   python mcp_client_example.py
   ```

## Integration Steps

### 1. Server Integration

To integrate Authed with your MCP server:

```python
from client.sdk import Authed
from mcp_authed_adapter import AuthedMCPServerAdapter

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

### 2. Client Integration

To integrate Authed with your MCP client:

```python
from client.sdk import Authed
from mcp_authed_adapter import AuthedMCPClientAdapter

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

### 3. Permission Management

Grant access from one agent to an MCP server:

```python
from mcp_authed_adapter import grant_mcp_access

# Grant access
success = await grant_mcp_access(
    authed=authed,
    client_agent_id="client-agent-id",
    server_agent_id="server-agent-id",
    permissions=["read", "execute"]  # Optional custom permissions
)
```

## Security Considerations

- Always use HTTPS for production deployments
- Implement token expiration and refresh mechanisms
- Validate all cryptographic signatures
- Maintain audit logs of authentication events
- Implement rate limiting to prevent abuse

## Next Steps

- Implement a full HTTP transport for the MCP server and client
- Add support for fine-grained permissions based on MCP operations
- Create monitoring and logging capabilities
- Propose extensions to the MCP specification for standardized authentication

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 