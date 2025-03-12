"""Test Agent A for WebSocket channel testing."""

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

from client.sdk.manager import Authed
from client.sdk.channel.protocol import MessageType
from client.sdk.server.websocket import WebSocketHandler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Test Agent A")

# Agent configuration
AGENT_ID = os.environ.get("AGENT_A_ID")
AGENT_SECRET = os.environ.get("AGENT_A_SECRET")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "https://api.getauthed.dev")

# Generate keys if not provided
PRIVATE_KEY = os.environ.get("AGENT_A_PRIVATE_KEY")
PUBLIC_KEY = os.environ.get("AGENT_A_PUBLIC_KEY")

if not AGENT_ID or not AGENT_SECRET:
    logger.error("AGENT_A_ID and AGENT_A_SECRET environment variables must be set")
    sys.exit(1)

# If keys are not provided, generate them
if not PRIVATE_KEY or not PUBLIC_KEY:
    logger.info("Generating new key pair for Agent A")
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    
    # Generate a new key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # Get the public key
    public_key = private_key.public_key()
    
    # Serialize the private key to PEM format
    PRIVATE_KEY = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    # Serialize the public key to PEM format
    PUBLIC_KEY = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    logger.info("Key pair generated successfully")

# Initialize the SDK
logger.info(f"Initializing SDK for Agent A with ID: {AGENT_ID}")
logger.info(f"Using registry URL: {REGISTRY_URL}")

try:
    sdk = Authed.initialize(
        registry_url=REGISTRY_URL,
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
        private_key=PRIVATE_KEY,
        public_key=PUBLIC_KEY
    )
    logger.info("SDK initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize SDK: {str(e)}")
    sys.exit(1)

# Create WebSocket handler
ws_handler = WebSocketHandler(authed_sdk=sdk)

# Message handlers
async def handle_text_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle text messages."""
    logger.info(f"Received text message: {message}")
    
    # Extract message content
    content_data = message["content"]["data"]
    text = content_data.get("text", "No text provided")
    
    # Create response
    response_data = {
        "text": f"Agent A received: {text}",
        "timestamp": ws_handler._get_iso_timestamp()
    }
    
    return {
        "type": MessageType.RESPONSE,
        "data": response_data
    }

# Register message handlers
ws_handler.register_handler(MessageType.REQUEST, handle_text_message)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for agent communication."""
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    
    try:
        # Handle the WebSocket connection
        await ws_handler.handle_connection(websocket, "/ws")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error handling WebSocket connection: {str(e)}")
        await websocket.close()

@app.get("/connect-to-agent-b")
async def connect_to_agent_b():
    """Connect to Agent B using WebSocket channel."""
    try:
        # Agent B information
        target_agent_id = os.environ.get("AGENT_B_ID")
        websocket_url = os.environ.get("AGENT_B_WS_URL", "ws://localhost:8001/ws")
        
        if not target_agent_id:
            return {
                "status": "error",
                "error": "AGENT_B_ID environment variable not set"
            }
        
        logger.info(f"Connecting to Agent B ({target_agent_id}) at {websocket_url}")
        
        # Connect to Agent B
        channel = await sdk.channels.connect_to_agent(
            target_agent_id=target_agent_id,
            channel_type="websocket",
            websocket_url=websocket_url
        )
        
        logger.info(f"Connected to Agent B ({target_agent_id})")
        
        # Send a message
        message_content = {
            "text": f"Hello from Agent A ({AGENT_ID})!",
            "timestamp": channel._get_iso_timestamp()
        }
        
        message_id = await channel.send_message(
            content_type=MessageType.REQUEST,
            content_data=message_content
        )
        
        logger.info(f"Sent message to Agent B with ID: {message_id}")
        
        # Wait for a response with timeout
        logger.info("Waiting for response from Agent B...")
        try:
            response = await asyncio.wait_for(
                channel.receive_message(),
                timeout=10.0
            )
            
            logger.info(f"Received response from Agent B: {response}")
            
            # Process the response
            if response and "content" in response:
                content_type = response["content"].get("type")
                content_data = response["content"].get("data", {})
                
                # Close the channel
                await channel.close("test_complete")
                logger.info("Channel to Agent B closed")
                
                # Return the response
                return {
                    "status": "success",
                    "message_sent": message_content,
                    "response_received": {
                        "type": content_type,
                        "data": content_data
                    }
                }
                
        except asyncio.TimeoutError:
            await channel.close("timeout")
            return {
                "status": "error",
                "error": "Timeout waiting for response from Agent B"
            }
            
    except Exception as e:
        logger.error(f"Error connecting to Agent B: {str(e)}")
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
        "service": "Agent A",
        "registry_url": REGISTRY_URL
    }

if __name__ == "__main__":
    # Run the server
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 