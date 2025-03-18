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
    old_token = "eyJhbGciOiJSUzI1NiIsImp3ayI6eyJhbGciOiJSUzI1NiIsImUiOiJBUUFCIiwia3R5IjoiUlNBIiwibiI6Im9QaWtOcnFHU0twSjNuS2pRaEhLYXRRajY2a0xPZGtCMEhiMVZ4RXVJZkRyLUpCUDI5eFJLS3R2SXlJS0hGX2IzQWFsQ3AtQnc4czVQWXZ6d1FfWkM4bTEtd29GY1A1RUlJSDF6QVoyNk12VTdGSEpRQ1RvajFGNFhfTkpZM2lvSURiRVhaekU3MmNTU1ZiaHVoRExjZ0EtWVFmaE1yOVJaeXYwbDd4aTNNVEw1aUNubV9TQ3dLblFheS0tNkwxYjQyMENIVkVKdjVVMUZDQnlmbHlTZWMtQ3VCYlJwOUxvODlfS0RjZ2l6cWNkSF81X2NyWTZ4TTZ3bmw0OVVSMWQtZEd4dU8xRkZwZW9pSHU2a2YwOUJwRFIxcEhEZnhoQThaMng3NkxULTJhR1F1OERUbkpMY0RHaWVfTVQ4YjFLNmlvcGVnRFRnemFyeTFwWWM1N3NEUSIsInVzZSI6InNpZyJ9LCJ0eXAiOiJkcG9wK2p3dCJ9.eyJqdGkiOiJmOGQ3Y2Y3ZS03NTczLTRkZGItYTE3MS0xMWM3NjNhODNlYTYiLCJodG0iOiJHRVQiLCJodHUiOiJodHRwOi8vbG9jYWxob3N0OjgwMDA6ODAwMC9zc2UiLCJpYXQiOjE3NDIyMjIwMDgsImV4cCI6MTc0MjIyMjMwOCwibm9uY2UiOiIzMzM4N2Y5OC1iZDU5LTQ3ZmItYTc0My1lYjNhZDIxYTM3MjYwMjdjMGY4Yi0zMmUzLTQ1In0.crTyN-OcGmC0tp-tT7vp2FJLCO6mj2xXaHg_WH5ZYU_S4RO224TlqmSZ3CPLP7I2wh4TrbjRfcaMxxd-ybm_mnS-uE74wlRV6l277NxSgjruplYtxVML9GfTcPyAQWPDVT9D8eKf-22lD-kHU6YqTOaFPCzWPV-LMhC-Y6gK10qKcH54ALbXSte0Po-w4izkRAlsHUwdi1Aw4AEkStk2IbPxGg6BelV1i4EpZAQnjdso7gxf_tEDemokebB17CEtx4AHhCcHkk6VPNp61ujXkqYXsuFNTTqnW9v-IX6JtWBs8wq5bO_FAdlYaaDC4ukh5aDCYgSvY6cipV2CcfzdPw', 'authorization': 'Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjYzcyNjJhNS00MDVkLTQxMDEtODAzMC0xZTM5MDRhNzEyNGUiLCJ0YXJnZXQiOiJlMzBjYmUxZS1jNDdjLTQwZTgtOGYwZi0wZmUzYmQzNTE4YWEiLCJkcG9wX2hhc2giOiI1MDMyOTU0YWIwZWI0MTI2NTcxNGY1YmVhYTRhZmI5OWI1NWNkNTFkM2MxMWNiMjY2YWZhYTVhYzg5NzlmNTFhIiwiZHBvcF9wdWJsaWNfa2V5IjoiMjAyNTAzMTZfMTg1NDEzOlowRkJRVUZCUW00eVJFczFSRGxYWTNaMU5WSmhiMGhxY0dKcWJGcHVZalIwU0VGS1QwWXhPVVZsVkdJelRHSXpNMHAxTFROYVdtZE9ia0ZTYnpGaFVXTmpka1ZmYjBKb2VHTTRaV2hRWTJaQk9UUkdNbVJIY25FNFRsSmFkWEZuVGpWMFRHdExkRTUyVDJkclVHWjBVekV4WTFNM1oycEVaRVJ2V25FdFIwOVhkbWxwWW1veE5ITm5lbmREVjJRd1VteEpSSEJFVmpjd2NqRjBhM0YyWm5GUVNURktNMmREUTA5RWJ5MURjRXB6YVRScmVWSXhRbGxHUm5kdWEyc3hhVEZ5T1hwYVRrZFFVMDVpTTE5ak5EUnJjak5tYUZOTFNFMHhSMjFITkZVMk0ydE9lV2d4U21wWE9XMU5aV1F4TkdzNU9EWkxXbDlTV21SRFoxbEphVFZMTmtwRGFrdHpVemd6TmxKSWRuUTNiVGhKVW5ReFRURmZhR3RQU1hkWVRrdEZUSEUwTmxkV1pWVnZTRTVWZHpsTWRtMUVWblpMVms5UExVeDRVM0YxZUdwalMxSmxUbUZ5VXpjMmNrcHBMVlo1Y1VWVlRtaHRVbGxPYUhVM1gycFpPV3AwYWpSeFZHVnNaMWxOYm1jelQyazFTbk5rTWpCeFNtSTRaSEZtY1hCMlpUZHRZMlpoYWtnNWRXeEhla3BtTFVvemVXNHlSRVZNZDFWMFpYZGZaMmxEVTNsZlNYRktZVkJJTFdOeVpUSmhNMVpWWDJOd1dWbzBUR1k1Y1hseVgzZExkbEpxVjBKTlh6TlhVbVpUUW1aVk4ybHRNR0k0TFRaS2FIWlhiemxFUWxWSWExWmhaMVoxTjBWNVJrTnRXazFzU0RVdGVGUnZjME4zVDFSRWVsRkNNRmxTWTJaWk9FNHhSRGwyWlZka1RXNTFhWE5SUkRCZlgzTTFWR2w1YW1WQ05YZGpkWEIzYldjME9XRm9ibG81U1RkT1gwVmtiVkpYZVdZeGFYWkJja2hhVFZOa2NrazJibUoxTUU5TGJrWktjME5SUW1ORVpXOXBYMGh2UVQwOSIsImV4cCI6MTc0MjIyMzgwOSwiaWF0IjoxNzQyMjIyMDA5LCJpc3MiOiJyZWdpc3RyeSIsImp0aSI6ImU4ZTkyMjBjLWZhY2QtNDM5Ny1iMDA1LTRlNTU2NzA3M2NmOCIsIm5iZiI6MTc0MjIyMjAwOSwidHlwIjoiaW50ZXJhY3Rpb25fdG9rZW4ifQ.U2knD6Or-yqoP6Wo2n20SdrJgUXirmpQXzP6vV0egKVraI2P-54C4SgfmDLHqGZvq6FFlYKuSzziwm9AiAMZgMK5yZ2cxE42B1x5u8iUhcseMWc_iJ05xJSyy9xOsseQwAw3oePrQU1llqply7I9WWJyKXap_33kkOYaJ2M9q3hvXh6VOS2Jq7gxFYoJYB0QzBEUwA7zo1pJRKB5yU7CUp-VWbIDakikv8Gr6KhFefyV9JnTPbdwC8daVabMINehTIbOn9VSTa-j7QDx01pMzdCLVQ-jKxdiqw9vSgKNnQLI6SQXgl9mZO_-CmwtpWBoSQ1OTUC3q6COOyQtBg_CXA"
    
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
