# Authed MCP Integration

This package provides integration between [Authed](https://getauthed.dev) authentication and the [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol).

## Overview

The Authed MCP integration allows you to:

1. Create MCP servers with Authed authentication
2. Create MCP clients that can authenticate with Authed
3. Register MCP servers as Authed agents
4. Grant access permissions between MCP clients and servers

## Installation

```bash
pip install authed-mcp
```

## Usage

### Server Example

```python
import asyncio
import os
from dotenv import load_dotenv

from authed import Authed
from authed_mcp import AuthedMCPServer

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize Authed client
    registry_url = os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev")
    agent_id = os.getenv("AUTHED_AGENT_ID")
    agent_secret = os.getenv("AUTHED_AGENT_SECRET")
    private_key = os.getenv("AUTHED_PRIVATE_KEY")
    public_key = os.getenv("AUTHED_PUBLIC_KEY")
    
    # Create MCP server with Authed authentication
    server = AuthedMCPServer(
        name="example-server",
        registry_url=registry_url,
        agent_id=agent_id,
        agent_secret=agent_secret,
        private_key=private_key,
        public_key=public_key
    )
    
    # Register a resource handler
    @server.resource("/hello/{name}")
    async def hello_resource(name: str):
        return f"Hello, {name}!", "text/plain"
    
    # Register a tool handler
    @server.tool("echo")
    async def echo_tool(message: str):
        return {"message": message}
    
    # Register a prompt handler
    @server.prompt("greeting")
    async def greeting_prompt(name: str = "World"):
        return f"Hello, {name}! Welcome to the MCP server."
    
    # Run the server
    server.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### Client Example

```python
import asyncio
import os
from dotenv import load_dotenv

from authed_mcp import AuthedMCPClient

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize client with Authed credentials
    registry_url = os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev")
    agent_id = os.getenv("AUTHED_AGENT_ID")
    agent_secret = os.getenv("AUTHED_AGENT_SECRET")
    private_key = os.getenv("AUTHED_PRIVATE_KEY")
    public_key = os.getenv("AUTHED_PUBLIC_KEY")
    
    # Create MCP client with Authed authentication
    client = AuthedMCPClient(
        registry_url=registry_url,
        agent_id=agent_id,
        agent_secret=agent_secret,
        private_key=private_key,
        public_key=public_key
    )
    
    # Get server agent ID
    server_agent_id = os.getenv("MCP_SERVER_AGENT_ID")
    
    # Define server URL
    server_url = "http://localhost:8000/sse"
    
    try:
        # Call a tool
        result = await client.call_tool(
            server_url=server_url,
            server_agent_id=server_agent_id,
            tool_name="echo",
            arguments={"message": "Hello from MCP client!"}
        )
        print(f"Echo result: {result}")
        
        # List available resources
        resources = await client.list_resources(
            server_url=server_url,
            server_agent_id=server_agent_id
        )
        print(f"Available resources: {resources}")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Components

### AuthedMCPServer

A wrapper around the MCP server that adds Authed authentication. It initializes both the Authed client and the MCP server, and registers the necessary middleware to handle authentication.

### AuthedMCPClient

A client for making authenticated requests to MCP servers. It automatically:
- Creates and attaches DPoP proofs to requests
- Handles token management
- Provides a simple interface for interacting with MCP servers
- Includes improved URL normalization for consistent comparison
- Provides robust error handling

## Utility Functions

### register_mcp_server

Registers an MCP server as an agent in Authed:

```python
from authed import Authed
from authed_mcp import register_mcp_server

async def setup():
    authed = Authed.initialize(...)
    
    server_info = await register_mcp_server(
        authed=authed,
        name="My MCP Server",
        description="MCP server with Authed authentication",
        capabilities={"tools": ["echo", "calculator"], "resources": ["hello"]}
    )
    
    # Save the resulting agent_id, private_key, etc.
    print(f"Server registered with ID: {server_info['agent_id']}")
```

### grant_mcp_access

Grants an MCP client access to an MCP server:

```python
from authed import Authed
from authed_mcp import grant_mcp_access

async def setup_permissions():
    authed = Authed.initialize(...)
    
    success = await grant_mcp_access(
        authed=authed,
        client_agent_id="client-agent-id",
        server_agent_id="server-agent-id",
        permissions=["mcp:call_tool", "mcp:list_resources"]
    )
    
    if success:
        print("Access granted successfully")
    else:
        print("Failed to grant access")
```

## Requirements

- Python 3.8+
- Authed SDK
- MCP SDK

## License

MIT 