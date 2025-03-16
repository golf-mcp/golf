"""
Test MCP client with an old Authed token.
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
    """Test with an old token."""
    # Define server URL
    server_url = "http://localhost:8000/sse"
    logger.info(f"Using server URL: {server_url}")
    
    # Use a hardcoded old token
    # This is a made-up token that should be invalid
    old_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjYzcyNjJhNS00MDVkLTQxMDEtODAzMC0xZTM5MDRhNzEyNGUiLCJ0YXJnZXQiOiJlMzBjYmUxZS1jNDdjLTQwZTgtOGYwZi0wZmUzYmQzNTE4YWEiLCJkcG9wX2hhc2giOiIwYzZmY2M3NjA5ZTdiNmUyZDczN2JjYTU2MThjYWZjNmEyZTY2YTZhZTYzMGViYzM4NWIyM2U5ZmIxMWM2ODUyIiwiZHBvcF9wdWJsaWNfa2V5IjoiOHFRUVM4clE1UEJpR1lvMHk4cHZjaGd4Umo3WU13T1hzQkc3TitwOXZRR0xBcUVMY3pvVTNlWnloQTE5dlA1U3hkR3JUOURHbXY3UkJGRXIzS0FNekFIQitWRVJBSlVCMEM1U3dwby9SVnFsNEJrQ25lblgxYnhoSDhGSTdybnFjalFPY1VkOXdVWkp5blFHUXBTZDNYUEE0UUVNdGh4RGtGNVozanQybW9rQTBhenExdE41bVM1RFNwNXVJQzhNSS84UFJTL0NzeE54MSthKzRqQnRmckRxTnNRR2dSb2pPbkI4NVZOcG9UcUlnaGl2UmoxSlZWNVphMkJFR3JkNUM1QnN4T1hwRXE0Y1NQZU0vdjZQWFljOTdRSTc5K2pSUGhZN20wK1BRMzRxZG00L0NMbSt5dmRpdEQwUnlNaXlPOFNUMFY3RzZQTk9lK1JqVjBVNEtTUXN4WFVBV3ZHQ2N0ZjZJd3hoVDhWNTlWUDY1STNieWNNdXdvMDdDc05BY0R4S05hVjJMUjNhME9uOWJzR2lKWFFrV3ZoK1JSNFlISHorYmsydWVPOUtVM3RDeEhELy9rbGtNSCsrSzZxc1YyVS9Tb1laQ1dYaldDVm5WYjVIWHRodDArRjErTDRLTXhNMWZuNHp0WlE3Vm1wQTNSN1Q3RmZFckZBTEVleHZvbm1VRnFWMFp0dnk5T3RraHVsZnJiSFB5K2RMLzRnQ2lUVUlIbmVMUU1jNWpSVHIiLCJleHAiOjE3NDIxMzc5MjUsImlhdCI6MTc0MjEzNjEyNSwiaXNzIjoicmVnaXN0cnkiLCJqdGkiOiJiY2U3YTBmNy1hZjUyLTRmYTQtOWUzNC1lZDg2NTQ4M2QzOWUiLCJuYmYiOjE3NDIxMzYxMjUsInR5cCI6ImludGVyYWN0aW9uX3Rva2VuIn0.hiW5L6cSOF4U7SYxgu1AyKJwhon2R8QVX50jKpx8rrKn-FmHKCu_A_B9Ty-79rC3IwABPg341zUrYiIyTinDTpaECgEWn6l3eoge_wkIMxqdUyojqhHJiq0tJh7fYzcY3Hh3_yDjkP87sZT1mOb28HM_OrEcIDdG2ZXVt5oHN96jb_BkA2QIXfFOLHr8LTyaZkm2_Ds5Gq4aTIZ-ZNGXJEWc3xRwYKN_9eeyI6zm3TLXgaPWYL4YNHO960cpQNAM6GDLArUIjG7AkzqrzAD0SewotCX1uRaVvzMHMnAsSrhOwfWTVgYFQxkbKvdSN4ND87z2E8CObz--IPBo-OSmmA"
    
    # Set up headers with the old token
    headers = {"Authorization": f"Bearer {old_token}"}
    logger.info(f"Using old token: {old_token[:20]}...")
    
    try:
        # Connect to the server with the old token
        logger.info("Connecting to server with old token...")
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
