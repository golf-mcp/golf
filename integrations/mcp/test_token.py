"""
Test script to create and verify a token separately.
This will help determine if the issue is with the registry or our MCP implementation.
"""

import asyncio
import json
import logging
import os
import pathlib
import httpx
import jwt
from uuid import UUID

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set Authed SDK logger to DEBUG
logging.getLogger('client.sdk').setLevel(logging.DEBUG)

async def create_token(registry_url, agent_id, agent_secret, private_key, target_agent_id):
    """Create a token for the target agent."""
    logger.info(f"Creating token for agent {agent_id} to interact with {target_agent_id}")
    
    # Create a DPoP proof for the token request
    from client.sdk.auth.dpop import DPoPHandler
    dpop_handler = DPoPHandler()
    
    token_url = f"{registry_url}/tokens/create"
    dpop_proof = dpop_handler.create_proof("POST", token_url, private_key)
    
    # Extract public key from private key
    from cryptography.hazmat.primitives import serialization
    private_key_obj = serialization.load_pem_private_key(
        private_key.encode(),
        password=None
    )
    public_key_obj = private_key_obj.public_key()
    public_key_pem = public_key_obj.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    # Remove header/footer and newlines for HTTP header
    public_key_clean = public_key_pem.replace('-----BEGIN PUBLIC KEY-----', '')
    public_key_clean = public_key_clean.replace('-----END PUBLIC KEY-----', '')
    public_key_clean = public_key_clean.replace('\n', '')
    
    logger.debug(f"Public key (original): {public_key_pem}")
    logger.debug(f"Public key (cleaned): {public_key_clean}")
    
    # Create token request
    headers = {
        "agent-id": agent_id,
        "dpop-public-key": public_key_clean,
        "content-type": "application/json"
    }
    
    data = {
        "target_agent_id": target_agent_id,
        "dpop_proof": dpop_proof
    }
    
    logger.debug(f"Token request headers: {headers}")
    logger.debug(f"Token request data: {data}")
    
    # Send request to create token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            token_url,
            headers=headers,
            json=data
        )
        
        logger.debug(f"Token response status: {response.status_code}")
        logger.debug(f"Token response: {response.text}")
        
        if response.status_code == 200:
            token_data = response.json()
            logger.info(f"Token created successfully: {token_data['token'][:20]}...")
            return token_data["token"]
        else:
            logger.error(f"Failed to create token: {response.text}")
            return None

async def verify_token(registry_url, token, private_key, target_agent_id=None):
    """Verify a token."""
    logger.info(f"Verifying token: {token[:20]}...")
    
    verify_url = f"{registry_url}/tokens/verify"
    
    # Create a new DPoP proof for verification
    from client.sdk.auth.dpop import DPoPHandler
    dpop_handler = DPoPHandler()
    dpop_proof = dpop_handler.create_proof("POST", verify_url, private_key)
    
    # Set up headers for verification
    headers = {
        "authorization": f"Bearer {token}",
        "dpop": dpop_proof
    }
    
    if target_agent_id:
        headers["target-agent-id"] = str(target_agent_id)
    
    logger.debug(f"Verify request headers: {headers}")
    
    # Send request to verify token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            verify_url,
            headers=headers
        )
        
        logger.debug(f"Verify response status: {response.status_code}")
        logger.debug(f"Verify response: {response.text}")
        
        if response.status_code == 200:
            logger.info("Token verified successfully")
            return True
        else:
            logger.error(f"Token verification failed: {response.text}")
            return False

async def main():
    """Run the token test."""
    # Load credentials from JSON file
    creds_path = pathlib.Path(__file__).parent / "credentials.json"
    
    try:
        with open(creds_path, "r") as f:
            creds = json.load(f)
            
        # Use agent_a as the requesting agent
        registry_url = os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev")
        agent_id = creds["agent_a_id"]
        agent_secret = creds["agent_a_secret"]
        private_key = creds["agent_a_private_key"]
        public_key = creds["agent_a_public_key"]
        
        # Use agent_b as the target agent
        target_agent_id = creds["agent_b_id"]
        
        logger.info(f"Loaded credentials for agent: {agent_id}")
        logger.info(f"Target agent: {target_agent_id}")
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error loading credentials: {str(e)}")
        return
    
    # Step 1: Create a token
    token = await create_token(
        registry_url,
        agent_id,
        agent_secret,
        private_key,
        target_agent_id
    )
    
    if not token:
        logger.error("Failed to create token, exiting")
        return
    
    # Step 2: Verify the token using the same private key
    verified = await verify_token(
        registry_url,
        token,
        private_key,
        target_agent_id
    )
    
    if verified:
        logger.info("Token verification successful")
    else:
        logger.error("Token verification failed")

if __name__ == "__main__":
    asyncio.run(main()) 