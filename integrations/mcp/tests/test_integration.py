"""
Test script for MCP-Authed integration.

This script runs both a server and client to test the integration.
"""

import asyncio
import logging
import os
import json
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import the integration
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from integrations.mcp import AuthedMCPServer, AuthedMCPClient

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default test credentials
TEST_CREDENTIALS = {
    "server": {
        "agent_id": "test-server-agent-id",
        "agent_secret": "test-server-agent-secret",
        "private_key": """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCg+KQ2uoZIqkne
cqNCEcpq1CPrqQs52QHQdvVXES4h8Ov4kE/b3FEoq28jIgocX9vcBqUKn4HDyzk9
i/PBD9kLybX7CgVw/kQggfXMBnboy9TsUclAJOiPUXhf80ljeKggNsRdnMTvZxJJ
VuG6EMtyAD5hB+Eyv1FnK/SXvGLcxMvmIKeb9ILAqdBrL77ovVvjbQIdUQm/lTUU
IHJ+XJJ5z4K4FtGn0ujz38oNyCLOpx0f/n9ytjrEzrCeXj1RHV350bG47UUWl6iI
e7qR/T0GkNHWkcN/GEDxnbHvotP7ZoZC7wNOcktwMaJ78xPxvUrqKil6ANODNqvL
WlhznuwNAgMBAAECggEABZNXLMYdLJspX9kcqocvObALZng+eUx48Z2NNezUajyM
D9n/yh/Bd+UoPlFJhF4VoXNheBK6TevWGbmlQcSowe3EreNU+Or1tSKLPvviVoHo
6B6VF/GvVHd/8eLdYeKmACeleZCaiahKS9wEiYtXYKV9g6LgO//AdBBjsnXF/tuM
GIDzLcv53C5tWaNI+lR5aorGcArjicxnSGYChSgbNI0+QUavB0bR3RFhQaCbhcvS
v7sLrbb64arqAZv/Jo9ZHfk0SXwrSzR/NGm9GcthGr4BJ8MyNXegACM7mfAqtDjg
3FxA9DYn5EFmPHf556PKgk4bKmRLpbIlh5SsmqjrQQKBgQDUqpedxiSNxvzwC1wE
dDjQyB1ZRnhjZ3ksmyawN/l7W5xkfl+7gZp7/V2QLoNWgwGtCnBTTX6R6W1C1Fc3
4wAFNlskBmd6SrhjB+nhDiwAVWBIMxGgQDrdN65jNn0h7YOQUuk5yRlJDM+tsyVi
+yP6OV4ikW35vt0Ody+cxF0MNQKBgQDBxXRS1FQrFvbo8BucDJnGFhoX8YmHXcE9
YvOQv2/n51cdfYAEj5HXNb+KDfkb3o2xi1DjqGnj4NEc+6Xy30jqGDvhhkNkd4ox
U1prRfZaAAHcN2wRIG8nwbCiRT2IDtX7b8i9g6TIYBRPsjl2XQh+sS3AB4jsCZ4L
M+PjrqJreQKBgBZCtRQixXjBt4A48CzXLYtNJyVNJxTgo+Jzax1O/qJW+IvcXpD2
BAGuh7ir5buMgwRl71QI7JLBaFpyd561+C6Tff7LXNGEOMDE90pDfX+bcDSeg93O
W1sElRB1h6uhfQACbb9KuYbX/HUmJ2ew+hcbIitkJarau7Dj8Ovr8gFxAoGAT18v
V+Jrm77rYt0/ofszXgWdqKMiv5Uy249Vz7vq/eYwM/89WiDpD2uPyuAQY08VYV18
w9Qvk816OtIF1ueJeYJ1vNp/bn7c13maNwjQcWtBV9BH7vgHMBTR4pZULxBMrJLM
enybGgzpJQAPM6HGIgc3g0pS1sTVvScDOTdGhpkCgYEAvZPXxdp7ojmY3uVybP0z
cSD93Aiky/SrvKedQ7GvBtq2X+nwM095vAowFdnOHAkCkQSW3A5gj3lgLcTyd0QV
cYEOdax7VIoenInl1efzurHufxOpS8vB+UsHST08gq0UpV22GHxYzHjQD8COVsQn
0TzfsoC5V9ybx7/OliCTzUw=
-----END PRIVATE KEY-----""",
        "public_key": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoPikNrqGSKpJ3nKjQhHK
atQj66kLOdkB0Hb1VxEuIfDr+JBP29xRKKtvIyIKHF/b3AalCp+Bw8s5PYvzwQ/Z
C8m1+woFcP5EIIH1zAZ26MvU7FHJQCToj1F4X/NJY3ioIDbEXZzE72cSSVbhuhDL
cgA+YQfhMr9RZyv0l7xi3MTL5iCnm/SCwKnQay++6L1b420CHVEJv5U1FCByflyS
ec+CuBbRp9Lo89/KDcgizqcdH/5/crY6xM6wnl49UR1d+dGxuO1FFpeoiHu6kf09
BpDR1pHDfxhA8Z2x76LT+2aGQu8DTnJLcDGie/MT8b1K6iopegDTgzary1pYc57s
DQIDAQAB
-----END PUBLIC KEY-----"""
    },
    "client": {
        "agent_id": "test-client-agent-id",
        "agent_secret": "test-client-agent-secret",
        "private_key": """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCg+KQ2uoZIqkne
cqNCEcpq1CPrqQs52QHQdvVXES4h8Ov4kE/b3FEoq28jIgocX9vcBqUKn4HDyzk9
i/PBD9kLybX7CgVw/kQggfXMBnboy9TsUclAJOiPUXhf80ljeKggNsRdnMTvZxJJ
VuG6EMtyAD5hB+Eyv1FnK/SXvGLcxMvmIKeb9ILAqdBrL77ovVvjbQIdUQm/lTUU
IHJ+XJJ5z4K4FtGn0ujz38oNyCLOpx0f/n9ytjrEzrCeXj1RHV350bG47UUWl6iI
e7qR/T0GkNHWkcN/GEDxnbHvotP7ZoZC7wNOcktwMaJ78xPxvUrqKil6ANODNqvL
WlhznuwNAgMBAAECggEABZNXLMYdLJspX9kcqocvObALZng+eUx48Z2NNezUajyM
D9n/yh/Bd+UoPlFJhF4VoXNheBK6TevWGbmlQcSowe3EreNU+Or1tSKLPvviVoHo
6B6VF/GvVHd/8eLdYeKmACeleZCaiahKS9wEiYtXYKV9g6LgO//AdBBjsnXF/tuM
GIDzLcv53C5tWaNI+lR5aorGcArjicxnSGYChSgbNI0+QUavB0bR3RFhQaCbhcvS
v7sLrbb64arqAZv/Jo9ZHfk0SXwrSzR/NGm9GcthGr4BJ8MyNXegACM7mfAqtDjg
3FxA9DYn5EFmPHf556PKgk4bKmRLpbIlh5SsmqjrQQKBgQDUqpedxiSNxvzwC1wE
dDjQyB1ZRnhjZ3ksmyawN/l7W5xkfl+7gZp7/V2QLoNWgwGtCnBTTX6R6W1C1Fc3
4wAFNlskBmd6SrhjB+nhDiwAVWBIMxGgQDrdN65jNn0h7YOQUuk5yRlJDM+tsyVi
+yP6OV4ikW35vt0Ody+cxF0MNQKBgQDBxXRS1FQrFvbo8BucDJnGFhoX8YmHXcE9
YvOQv2/n51cdfYAEj5HXNb+KDfkb3o2xi1DjqGnj4NEc+6Xy30jqGDvhhkNkd4ox
U1prRfZaAAHcN2wRIG8nwbCiRT2IDtX7b8i9g6TIYBRPsjl2XQh+sS3AB4jsCZ4L
M+PjrqJreQKBgBZCtRQixXjBt4A48CzXLYtNJyVNJxTgo+Jzax1O/qJW+IvcXpD2
BAGuh7ir5buMgwRl71QI7JLBaFpyd561+C6Tff7LXNGEOMDE90pDfX+bcDSeg93O
W1sElRB1h6uhfQACbb9KuYbX/HUmJ2ew+hcbIitkJarau7Dj8Ovr8gFxAoGAT18v
V+Jrm77rYt0/ofszXgWdqKMiv5Uy249Vz7vq/eYwM/89WiDpD2uPyuAQY08VYV18
w9Qvk816OtIF1ueJeYJ1vNp/bn7c13maNwjQcWtBV9BH7vgHMBTR4pZULxBMrJLM
enybGgzpJQAPM6HGIgc3g0pS1sTVvScDOTdGhpkCgYEAvZPXxdp7ojmY3uVybP0z
cSD93Aiky/SrvKedQ7GvBtq2X+nwM095vAowFdnOHAkCkQSW3A5gj3lgLcTyd0QV
cYEOdax7VIoenInl1efzurHufxOpS8vB+UsHST08gq0UpV22GHxYzHjQD8COVsQn
0TzfsoC5V9ybx7/OliCTzUw=
-----END PRIVATE KEY-----""",
        "public_key": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoPikNrqGSKpJ3nKjQhHK
atQj66kLOdkB0Hb1VxEuIfDr+JBP29xRKKtvIyIKHF/b3AalCp+Bw8s5PYvzwQ/Z
C8m1+woFcP5EIIH1zAZ26MvU7FHJQCToj1F4X/NJY3ioIDbEXZzE72cSSVbhuhDL
cgA+YQfhMr9RZyv0l7xi3MTL5iCnm/SCwKnQay++6L1b420CHVEJv5U1FCByflyS
ec+CuBbRp9Lo89/KDcgizqcdH/5/crY6xM6wnl49UR1d+dGxuO1FFpeoiHu6kf09
BpDR1pHDfxhA8Z2x76LT+2aGQu8DTnJLcDGie/MT8b1K6iopegDTgzary1pYc57s
DQIDAQAB
-----END PUBLIC KEY-----"""
    }
}

# Server configuration
SERVER_PORT = 8765
SERVER_HOST = "localhost"
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# Mock Authed registry for testing
class MockAuthedRegistry:
    """Mock Authed registry for testing."""
    
    def __init__(self):
        """Initialize the mock registry."""
        self.tokens = {}
        self.permissions = {}
    
    async def verify_request(self, method, url, headers):
        """Verify a request."""
        # For testing, we'll just return True
        return True
    
    async def get_interaction_token(self, target_id):
        """Get an interaction token."""
        # For testing, we'll just return a dummy token
        token = f"test-token-for-{target_id}"
        self.tokens[target_id] = token
        return token

# Server implementation
async def run_server():
    """Run the MCP server."""
    logger.info("Starting MCP server...")
    
    # Create a server with test credentials
    server_creds = TEST_CREDENTIALS["server"]
    
    # Create a mock Authed instance
    mock_authed = type("MockAuthed", (), {
        "auth": MockAuthedRegistry(),
        "initialize": lambda *args, **kwargs: mock_authed
    })
    
    # Create MCP server
    server = AuthedMCPServer(
        name="test-server",
        registry_url="https://mock-registry.example.com",
        agent_id=server_creds["agent_id"],
        agent_secret=server_creds["agent_secret"],
        private_key=server_creds["private_key"],
        public_key=server_creds["public_key"]
    )
    
    # Override the Authed instance with our mock
    server.authed = mock_authed
    
    # Register a resource handler
    @server.resource("/hello/{name}")
    async def hello_resource(name: str):
        logger.info(f"Resource request for name: {name}")
        return f"Hello, {name}!", "text/plain"
    
    # Register a tool handler
    @server.tool("echo")
    async def echo_tool(message: str):
        logger.info(f"Tool request with message: {message}")
        return {"message": message}
    
    # Register a prompt handler
    @server.prompt("greeting")
    async def greeting_prompt(name: str = "World"):
        logger.info(f"Prompt request for name: {name}")
        return f"Hello, {name}! Welcome to the MCP server."
    
    # Run the server
    await server.run(host=SERVER_HOST, port=SERVER_PORT)

# Client implementation
async def run_client():
    """Run the MCP client."""
    logger.info("Starting MCP client...")
    
    # Wait for server to start
    await asyncio.sleep(2)
    
    # Create a client with test credentials
    client_creds = TEST_CREDENTIALS["client"]
    
    # Create a mock Authed instance
    mock_authed = type("MockAuthed", (), {
        "auth": MockAuthedRegistry(),
        "initialize": lambda *args, **kwargs: mock_authed
    })
    
    # Create MCP client
    client = AuthedMCPClient(
        registry_url="https://mock-registry.example.com",
        agent_id=client_creds["agent_id"],
        agent_secret=client_creds["agent_secret"],
        private_key=client_creds["private_key"],
        public_key=client_creds["public_key"]
    )
    
    # Override the Authed instance with our mock
    client.authed = mock_authed
    
    try:
        # Call a tool
        logger.info("Calling echo tool...")
        result = await client.call_tool(
            server_url=SERVER_URL,
            server_agent_id=TEST_CREDENTIALS["server"]["agent_id"],
            tool_name="echo",
            arguments={"message": "Hello from MCP client!"}
        )
        logger.info(f"Echo result: {result}")
        
        # Get a prompt
        logger.info("Getting greeting prompt...")
        prompt = await client.get_prompt(
            server_url=SERVER_URL,
            server_agent_id=TEST_CREDENTIALS["server"]["agent_id"],
            prompt_name="greeting",
            arguments={"name": "MCP Client"}
        )
        logger.info(f"Greeting prompt: {prompt}")
        
        # Read a resource
        logger.info("Reading hello resource...")
        content, mime_type = await client.read_resource(
            server_url=SERVER_URL,
            server_agent_id=TEST_CREDENTIALS["server"]["agent_id"],
            resource_id="/hello/MCP"
        )
        logger.info(f"Resource content: {content} ({mime_type})")
        
        logger.info("All tests passed!")
        return True
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return False

async def main():
    """Run the integration test."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="Test MCP-Authed integration")
    parser.add_argument("--server-only", action="store_true", help="Run only the server")
    parser.add_argument("--client-only", action="store_true", help="Run only the client")
    args = parser.parse_args()
    
    # Run server and client
    if args.server_only:
        await run_server()
    elif args.client_only:
        success = await run_client()
        sys.exit(0 if success else 1)
    else:
        # Run both server and client
        server_task = asyncio.create_task(run_server())
        client_task = asyncio.create_task(run_client())
        
        # Wait for client to finish
        try:
            success = await client_task
            # Cancel server task
            server_task.cancel()
            sys.exit(0 if success else 1)
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(main()) 