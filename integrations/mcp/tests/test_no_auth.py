"""
Test MCP client without Authed authentication.
"""

import asyncio
import logging
from mcp import ClientSession
from mcp.client.sse import sse_client

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Test without authentication."""
    # Define server URL
    server_url = "http://localhost:8000/sse"
    logger.info(f"Using server URL: {server_url}")
    
    # No authentication headers
    headers = {}
    logger.info("Not using any authentication")
    
    try:
        # Connect to the server without authentication
        logger.info("Connecting to server without authentication...")
        async with sse_client(url=server_url, headers=headers) as streams:
            logger.info("SSE connection established, initializing MCP session")
            session = ClientSession(*streams)
            await session.initialize()
            
            # Try to list resources
            logger.info("Listing resources...")
            resources = await session.list_resources()
            logger.info(f"Resources: {resources}")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        logger.exception(e)

if __name__ == "__main__":
    asyncio.run(main())
