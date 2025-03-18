"""
Simple MCP Client Example

This example demonstrates how to create and use an MCP client with Authed authentication
using the new simplified API.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
import sys
from pathlib import Path

# Add the project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Now use direct imports
from integrations.mcp.client import create_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Run a simple MCP client with Authed authentication."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Get server URL and ID from environment or defaults
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/sse")
    server_agent_id = os.getenv("MCP_SERVER_AGENT_ID")
    
    if not server_agent_id:
        logger.error("MCP_SERVER_AGENT_ID environment variable is required")
        return
    
    # Create the client with values from environment variables
    try:
        client = await create_client()
        logger.info("Client created successfully")
        
        # List available resources
        logger.info(f"Listing resources from {server_url}...")
        resources = await client.list_resources(server_url, server_agent_id)
        logger.info(f"Found {len(resources)} resources:")
        for resource in resources:
            logger.info(f"  - {resource.path}")
        
        # List available tools
        logger.info(f"Listing tools from {server_url}...")
        tools = await client.list_tools(server_url, server_agent_id)
        logger.info(f"Found {len(tools)} tools:")
        for tool in tools:
            logger.info(f"  - {tool.name}")
        
        # Call the echo tool
        logger.info("Calling 'echo' tool...")
        echo_result = await client.call_tool(
            server_url=server_url,
            server_agent_id=server_agent_id,
            tool_name="echo",
            arguments={"message": "Hello from the MCP client!"}
        )
        logger.info(f"Echo result: {echo_result}")
        
        # Call the add tool if available
        try:
            logger.info("Calling 'add' tool...")
            add_result = await client.call_tool(
                server_url=server_url,
                server_agent_id=server_agent_id,
                tool_name="add",
                arguments={"a": 5, "b": 7}
            )
            logger.info(f"Add result: {add_result}")
        except Exception as e:
            logger.warning(f"Could not call 'add' tool: {str(e)}")
        
        # Read the hello resource
        try:
            logger.info("Reading 'hello/world' resource...")
            content, mime_type = await client.read_resource(
                server_url=server_url,
                server_agent_id=server_agent_id,
                resource_id="hello/world"
            )
            logger.info(f"Resource content ({mime_type}): {content}")
        except Exception as e:
            logger.warning(f"Could not read 'hello/world' resource: {str(e)}")
        
        return client
        
    except ValueError as e:
        logger.error(f"Failed to create client: {str(e)}")
    except Exception as e:
        logger.error(f"Error using client: {str(e)}")
        logger.exception(e)
    
    return None

if __name__ == "__main__":
    asyncio.run(main()) 