"""
Simple MCP Server Example

This example demonstrates how to create and run an MCP server with Authed authentication
using the new simplified API.
"""

import logging
from dotenv import load_dotenv
import sys
from pathlib import Path

# Add the project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Now use direct imports
from integrations.mcp.server import create_server, run_server, register_default_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run a simple MCP server with Authed authentication."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Create the server with values from environment variables
    try:
        server = create_server(name="simple-example-server")
        logger.info("Server created successfully")
        
        # Register default handlers for demo purposes
        register_default_handlers(server)
        logger.info("Default handlers registered")
        
        # Or register your own custom handlers
        @server.resource("custom/{id}")
        async def custom_resource(id: str):
            return f"Custom resource with ID: {id}", "text/plain"
        
        @server.tool("add")
        async def add_tool(a: int, b: int):
            return {"result": a + b}
        
        # Run the server
        logger.info("Starting server...")
        run_server(server, host="0.0.0.0", port=8000)
        
        # Note: This line will only be reached when the server is stopped
        return server
    except ValueError as e:
        logger.error(f"Failed to create server: {str(e)}")
    except Exception as e:
        logger.error(f"Error running server: {str(e)}")
        logger.exception(e)
    
    return None

if __name__ == "__main__":
    main() 