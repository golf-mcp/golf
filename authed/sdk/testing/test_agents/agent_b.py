"""Test Agent B for WebSocket channel testing."""

import logging
import os
import sys
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
from typing import Dict, Any
import asyncio
from contextlib import asynccontextmanager

# Add parent directories to path to import SDK
# Make sure the local development version takes precedence
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from authed.sdk.channel import Channel
from authed.sdk.channel.protocol import MessageType

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler."""
    # Startup: Run when the application starts
    logger.info(f"Agent B started with ID: {AGENT_ID}")
    logger.info(f"Listening on port: {PORT}")
    
    # If Agent A info is provided, initiate a connection
    if AGENT_A_ID and AGENT_A_WS_URL:
        # Start the connection task in the background
        asyncio.create_task(connect_to_agent_a())
    
    yield  # This is where the application runs
    
    # Shutdown: Run when the application is shutting down
    logger.info("Agent B shutting down")

app = FastAPI(title="Test Agent B", lifespan=lifespan)

# Agent configuration
AGENT_ID = os.environ.get("AGENT_B_ID")
AGENT_SECRET = os.environ.get("AGENT_B_SECRET")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "https://api.getauthed.dev")

# Get keys if provided
PRIVATE_KEY = os.environ.get("AGENT_B_PRIVATE_KEY")
PUBLIC_KEY = os.environ.get("AGENT_B_PUBLIC_KEY")

# Target agent information
AGENT_A_ID = os.environ.get("AGENT_A_ID")
AGENT_A_WS_URL = os.environ.get("AGENT_A_WS_URL", "http://localhost:8000/ws")

# Port for this agent
PORT = int(os.environ.get("PORT", 8001))

# Check required environment variables
if not AGENT_ID or not AGENT_SECRET:
    logger.error("AGENT_B_ID and AGENT_B_SECRET environment variables must be set")
    sys.exit(1)

# Create a custom message handler
async def handle_text_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle text messages."""
    # Extract message content
    content_data = message["content"]["data"]
    text = content_data.get("text", "No text provided")
    
    logger.info(f"Agent B received message: {text}")
    
    # Create response
    response_data = {
        "text": f"Agent B received: {text}",
        "timestamp": agent.get_iso_timestamp()
    }
    
    return {
        "type": MessageType.RESPONSE,
        "data": response_data
    }

# Create the agent
agent = Channel(
    agent_id=AGENT_ID,
    agent_secret=AGENT_SECRET,
    registry_url=REGISTRY_URL,
    private_key=PRIVATE_KEY,
    public_key=PUBLIC_KEY
)

# Register the message handler
agent.register_handler(MessageType.REQUEST, handle_text_message)

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections."""
    await websocket.accept()  # Accept the connection first
    try:
        await agent.handle_websocket(websocket, "/ws")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        # Connection might already be closed, but try to close it gracefully
        try:
            await websocket.close()
        except:
            pass

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

# Connect to Agent A endpoint
@app.get("/connect-to-agent-a")
async def connect_to_agent_a_endpoint():
    """Endpoint to test connection to Agent A."""
    try:
        # Open a channel to Agent A
        channel = await agent.open_channel(
            target_agent_id=AGENT_A_ID,
            websocket_url=AGENT_A_WS_URL
        )
        
        # Send a test message
        content_data = {
            "text": "Hello from Agent B! This is a test message from the /connect-to-agent-a endpoint.",
            "timestamp": agent.get_iso_timestamp()
        }
        
        message_id = await agent.send_message(
            channel=channel,
            content_type=MessageType.REQUEST,
            content_data=content_data
        )
        
        # Wait for a response
        response = await agent.receive_message(channel, timeout=5.0)
        
        # Extract response text
        response_text = response["content"]["data"].get("text", "")
        
        # Close the channel
        await agent.close_channel(channel)
        
        return {
            "status": "success",
            "message_id": message_id,
            "response": response_text
        }
    except Exception as e:
        logger.error(f"Error connecting to Agent A: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

async def connect_to_agent_a():
    """Connect to Agent A and send a test message."""
    try:
        # Wait a bit for Agent A to start
        await asyncio.sleep(3)
        
        logger.info(f"Connecting to Agent A ({AGENT_A_ID}) at {AGENT_A_WS_URL}")
        
        # Open a channel to Agent A
        channel = await agent.open_channel(
            target_agent_id=AGENT_A_ID,
            websocket_url=AGENT_A_WS_URL
        )
        
        logger.info("Channel opened successfully")
        
        # Send a test message
        content_data = {
            "text": "Hello from Agent B! This is an automated test message.",
            "timestamp": agent.get_iso_timestamp()
        }
        
        message_id = await agent.send_message(
            channel=channel,
            content_type=MessageType.REQUEST,
            content_data=content_data
        )
        
        logger.info(f"Test message sent with ID: {message_id}")
        
        # Wait for a response
        response = await agent.receive_message(channel, timeout=5.0)
        
        # Extract and log the response text
        response_text = response["content"]["data"].get("text", "")
        logger.info(f"Received response from Agent A: {response_text}")
        
        # Keep the channel open for future messages
        
    except Exception as e:
        logger.error(f"Error connecting to Agent A: {e}")

# Run the server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT) 