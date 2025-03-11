import asyncio
import os
import httpx
from client.sdk.manager import Authed
from client.sdk.config import AuthedConfig
from client.sdk.decorators.outgoing.httpx import protect_httpx

async def test_both_methods():
    """Test both initialization methods."""
    print("\nTesting old initialization method...")
    try:
        config = AuthedConfig.from_env()
        Authed.initialize(
            registry_url=config.registry_url,
            agent_id=config.agent_id,
            agent_secret=config.agent_secret,
            private_key=config.private_key,
            public_key=config.public_key
        )
        manager = Authed.get_instance()
        print("✓ Old method successful")
    except Exception as e:
        print(f"✗ Old method failed: {str(e)}")
        return

    print("\nTesting new initialization method...")
    try:
        auth = Authed.from_env()
        print("✓ New method successful")
    except Exception as e:
        print(f"✗ New method failed: {str(e)}")
        return

    print("\nTesting basic health check...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{os.getenv('AUTHED_REGISTRY_URL')}/health")
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
            if response.status_code == 200:
                print(f"✓ Health check successful (status code: {response.status_code})")
            else:
                print(f"✗ Health check failed (status code: {response.status_code})")
    except Exception as e:
        print(f"✗ Health check failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_both_methods()) 