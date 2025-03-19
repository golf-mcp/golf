"""Test Agent A for WebSocket channel testing."""

import logging
import os
import sys
from pathlib import Path
from fastapi import FastAPI, WebSocket
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

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler."""
    # Startup: Run when the application starts
    logger.info(f"Agent A started with ID: {AGENT_ID}")
    logger.info(f"Listening on port: {PORT}")
    
    # If Agent B info is provided, initiate a connection
    if AGENT_B_ID and AGENT_B_WS_URL:
        # Start the connection task in the background
        asyncio.create_task(connect_to_agent_b())
    
    yield  # This is where the application runs
    
    # Shutdown: Run when the application is shutting down
    logger.info("Agent A shutting down")

# Create FastAPI app with lifespan
app = FastAPI(title="Test Agent A", lifespan=lifespan)

# Agent configuration
AGENT_ID = os.environ.get("AGENT_A_ID")
AGENT_SECRET = os.environ.get("AGENT_A_SECRET")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "https://api.getauthed.dev")

# Get keys if provided
PRIVATE_KEY = os.environ.get("AGENT_A_PRIVATE_KEY")
PUBLIC_KEY = os.environ.get("AGENT_A_PUBLIC_KEY")

# Target agent information
AGENT_B_ID = os.environ.get("AGENT_B_ID")
AGENT_B_WS_URL = os.environ.get("AGENT_B_WS_URL", "http://localhost:8001/ws")

# Port for this agent
PORT = int(os.environ.get("PORT", 8000))

# Check required environment variables
if not AGENT_ID or not AGENT_SECRET:
    logger.error("AGENT_A_ID and AGENT_A_SECRET environment variables must be set")
    sys.exit(1)

# Create a custom message handler
async def handle_text_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle text messages."""
    # Extract message content
    content_data = message["content"]["data"]
    text = content_data.get("text", "No text provided")
    
    logger.info(f"Agent A received message: {text}")
    
    # Create response
    response_data = {
        "text": f"Agent A received: {text}",
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

# Connect to Agent B endpoint
@app.get("/connect-to-agent-b")
async def connect_to_agent_b_endpoint():
    """Endpoint to test connection to Agent B."""
    try:
        # Open a channel to Agent B
        channel = await agent.open_channel(
            target_agent_id=AGENT_B_ID,
            websocket_url=AGENT_B_WS_URL
        )
        
        # Send a test message
        content_data = {
            "text": "Hello from Agent A! This is a test message from the /connect-to-agent-b endpoint.",
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
        logger.error(f"Error connecting to Agent B: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

async def connect_to_agent_b():
    """Connect to Agent B and send a test message."""
    try:
        # Wait a bit for Agent B to start
        await asyncio.sleep(2)
        
        logger.info(f"Connecting to Agent B ({AGENT_B_ID}) at {AGENT_B_WS_URL}")
        
        # Open a channel to Agent B
        channel = await agent.open_channel(
            target_agent_id=AGENT_B_ID,
            websocket_url=AGENT_B_WS_URL
        )
        
        logger.info("Channel opened successfully")
        
        # Send a test message
        content_data = {
            "text": "Hello from Agent A! This is an automated test message.",
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
        logger.info(f"Received response from Agent B: {response_text}")
        
        # Keep the channel open for future messages
        
    except Exception as e:
        logger.error(f"Error connecting to Agent B: {e}")

# Run the server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT) 