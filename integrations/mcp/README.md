# Authed MCP Integration

This package provides integration between [Authed](https://authed.ai) authentication and the [Model Context Protocol (MCP)](https://github.com/mcp-sdk/mcp).

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

from client.sdk import Authed
from integrations.mcp import AuthedMCPServer

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize Authed client
    authed = Authed(
        api_key=os.getenv("AUTHED_API_KEY"),
        api_url=os.getenv("AUTHED_API_URL", "https://api.authed.ai")
    )
    
    # Create MCP server with Authed authentication
    server = AuthedMCPServer("example-server", authed)
    
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
    await server.run(host="localhost", port=8000)

if __name__ == "__main__":
    asyncio.run(main())
```

### Client Example

```python
import asyncio
import os
from dotenv import load_dotenv

from client.sdk import Authed
from integrations.mcp import AuthedMCPClient, grant_mcp_access

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize Authed client
    authed = Authed(
        api_key=os.getenv("AUTHED_API_KEY"),
        api_url=os.getenv("AUTHED_API_URL", "https://api.authed.ai")
    )
    
    # Create MCP client with Authed authentication
    client = AuthedMCPClient(authed)
    
    # Get server agent ID (from running the server example)
    server_agent_id = os.getenv("MCP_SERVER_AGENT_ID")
    
    # Define server URL
    server_url = "http://localhost:8000"
    
    # Call a tool
    result = await client.call_tool(
        server_url=server_url,
        server_agent_id=server_agent_id,
        tool_name="echo",
        arguments={"message": "Hello from MCP client!"}
    )
    print(f"Echo result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Components

### AuthedMCPServer

A wrapper around the MCP server that adds Authed authentication.

### AuthedMCPClient

A client for making authenticated requests to MCP servers.

### AuthedMCPServerMiddleware

Middleware for MCP servers to use Authed for authentication.

### register_mcp_server

Function to register an MCP server as an agent in Authed.

### grant_mcp_access

Function to grant an MCP client access to an MCP server.

## Requirements

- Python 3.8+
- Authed SDK
- MCP SDK

## License

MIT 