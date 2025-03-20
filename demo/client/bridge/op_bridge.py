import asyncio
import os
import sys
import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded environment variables from {dotenv_path}")
else:
    print(f"Warning: .env file not found at {dotenv_path}")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from ..op_client_authed import OnePasswordAuthedClient

logger.info("Initializing MCP bridge server...")

# Initialize FastMCP server
mcp = FastMCP("op-bridge")

# Initialize the 1Password Authed client
op_client = OnePasswordAuthedClient()

@mcp.tool()
async def onepassword_list_vaults() -> List[Dict[str, str]]:
    """List all available 1Password vaults"""
    logger.info("Tool called: onepassword_list_vaults")
    # Forward the request to the Authed-protected MCP server
    return await op_client.list_vaults()

@mcp.tool()
async def onepassword_list_items(vault_id: str) -> List[Dict[str, str]]:
    """List all items in a 1Password vault"""
    logger.info(f"Tool called: onepassword_list_items(vault_id={vault_id})")
    # Forward the request to the Authed-protected MCP server
    return await op_client.list_items(vault_id)

@mcp.tool()
async def onepassword_get_secret(vault_id: str, item_id: str, field_name: Optional[str] = None) -> Any:
    """Get a secret from 1Password"""
    logger.info(f"Tool called: onepassword_get_secret(vault_id={vault_id}, item_id={item_id}, field_name={field_name})")
    # Forward the request to the Authed-protected MCP server
    return await op_client.get_secret(vault_id, item_id, field_name)

# Add a health check tool
@mcp.tool()
async def health() -> Dict[str, str]:
    """Check the health of the bridge and underlying Authed service"""
    logger.info("Tool called: health")
    try:
        # Try to list vaults as a health check
        vaults = await op_client.list_vaults()
        status = {
            "status": "ok",
            "vaults_count": str(len(vaults)),
            "message": "Successfully connected to 1Password through Authed"
        }
        logger.info(f"Health check successful: {status}")
        return status
    except Exception as e:
        error_msg = f"Error connecting to 1Password: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg
        }

async def main():
    """Run the entire bridge in a single asyncio context."""
    try:
        # First connect to the 1Password service
        logger.info("Connecting to Authed-protected 1Password service...")
        await op_client.connect()
        logger.info("Successfully connected to Authed-protected 1Password service")
        
        # Check health
        health_result = await health()
        if health_result["status"] == "ok":
            logger.info("Health check passed")
            print("\n=== 1Password MCP Bridge ===")
            print("✅ Connected to 1Password service")
            print("Ready for connections from Cursor\n")
        else:
            logger.warning(f"Health check warning: {health_result['message']}")
        
        # Run the MCP server with stdio transport
        logger.info("Starting MCP bridge server with stdio transport...")
        await mcp.run_stdio_async()
    except Exception as e:
        logger.error(f"Error running the MCP bridge: {str(e)}")
        sys.exit(1)
    finally:
        # Clean up the client
        await op_client.cleanup()

if __name__ == "__main__":
    # Run everything in a single asyncio event loop
    asyncio.run(main()) 