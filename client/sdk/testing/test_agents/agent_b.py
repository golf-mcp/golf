"""Test Agent B for WebSocket channel testing."""

import asyncio
import logging
import os
import sys
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
from typing import Dict, Any

# Add parent directories to path to import SDK
# Make sure the local development version takes precedence
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from client.sdk import ChannelAgent, MessageType

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Test Agent B")

# Agent configuration
AGENT_ID = os.environ.get("AGENT_B_ID")
AGENT_SECRET = os.environ.get("AGENT_B_SECRET")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "https://api.getauthed.dev")

# Generate keys if not provided
PRIVATE_KEY = os.environ.get("AGENT_B_PRIVATE_KEY")
PUBLIC_KEY = os.environ.get("AGENT_B_PUBLIC_KEY")

if not AGENT_ID or not AGENT_SECRET:
    logger.error("AGENT_B_ID and AGENT_B_SECRET environment variables must be set")
    sys.exit(1)

# If keys are not provided, generate them
if not PRIVATE_KEY or not PUBLIC_KEY:
    logger.info("Generating new key pair for Agent B")
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    
    # Generate a new key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # Get the private key in PEM format
    PRIVATE_KEY = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    # Get the public key in PEM format
    PUBLIC_KEY = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    logger.info("Generated new key pair for Agent B")

# Create a custom message handler
async def handle_text_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle text messages."""
    # Extract message content
    content_data = message["content"]["data"]
    text = content_data.get("text", "No text provided")
    
    # Create response
    response_data = {
        "text": f"Agent B received: {text}",
        "timestamp": agent.get_iso_timestamp()
    }
    
    return {
        "type": MessageType.RESPONSE,
        "data": response_data
    }

# Create the agent using ChannelAgent
agent = ChannelAgent(
    agent_id=AGENT_ID,
    agent_secret=AGENT_SECRET,
    registry_url=REGISTRY_URL,
    private_key=PRIVATE_KEY,
    public_key=PUBLIC_KEY,
    handlers={
        MessageType.REQUEST: handle_text_message
    }
)

# Set up the WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for agent communication."""
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    
    try:
        # Handle the WebSocket connection
        await agent.handle_websocket(websocket, "/ws")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error handling WebSocket connection: {str(e)}")
        await websocket.close()

@app.get("/connect-to-agent-a")
async def connect_to_agent_a():
    """Connect to Agent A using WebSocket channel."""
    try:
        # Agent A information
        target_agent_id = os.environ.get("AGENT_A_ID")
        websocket_url = os.environ.get("AGENT_A_WS_URL", "ws://localhost:8000/ws")
        
        if not target_agent_id:
            return {
                "status": "error",
                "error": "AGENT_A_ID environment variable not set"
            }
        
        logger.info(f"Connecting to Agent A ({target_agent_id}) at {websocket_url}")
        
        # Send a text message to Agent A
        response = await agent.send_text_message(
            target_agent_id=target_agent_id,
            websocket_url=websocket_url,
            text="Hello from Agent B!"
        )
        
        # Process the response
        if response and "content" in response:
            content_type = response["content"].get("type")
            content_data = response["content"].get("data", {})
            
            return {
                "status": "success",
                "message_sent": "Hello from Agent B!",
                "response_type": content_type,
                "response_data": content_data
            }
        else:
            return {
                "status": "error",
                "error": "No valid response received"
            }
            
    except Exception as e:
        logger.error(f"Error connecting to Agent A: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent_id": AGENT_ID,
        "service": "Test Agent B"
    }

if __name__ == "__main__":
    # Run the server
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port) 