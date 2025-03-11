"""Example of using WebSocket channel for agent communication."""

import asyncio
import logging
import sys
import os
from typing import Dict, Any

# Add parent directory to path to import SDK
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from client.sdk.manager import Authed
from client.sdk.exceptions import ChannelError, ConnectionError, MessageError
from client.sdk.channel.protocol import MessageType, AgentChannelProtocol

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def send_and_receive(channel: AgentChannelProtocol, message_text: str) -> None:
    """Send a message and wait for a response.
    
    This function demonstrates how to use any channel that implements
    the AgentChannelProtocol, regardless of the specific implementation.
    
    Args:
        channel: Any channel implementing AgentChannelProtocol
        message_text: Text message to send
    """
    # Send a message
    message_content = {
        "text": message_text
    }
    
    message_id = await channel.send_message(
        content_type=MessageType.TEXT,
        content_data=message_content
    )
    
    logger.info(f"Sent message with ID: {message_id}")
    
    # Wait for a response with timeout
    logger.info("Waiting for response...")
    try:
        # Set a timeout for receiving a message
        response = await asyncio.wait_for(
            channel.receive_message(),
            timeout=10.0
        )
        
        logger.info(f"Received response: {response}")
        
        # Process the response
        if response and "content" in response:
            content_type = response["content"].get("type")
            content_data = response["content"].get("data", {})
            
            logger.info(f"Response type: {content_type}")
            logger.info(f"Response data: {content_data}")
            
    except asyncio.TimeoutError:
        logger.warning("Timeout waiting for response")

async def main():
    """Run the WebSocket channel example."""
    try:
        # Initialize the SDK
        # Replace with your actual values
        sdk = Authed.initialize(
            registry_url="https://registry.example.com",
            agent_id="your-agent-id",
            agent_secret="your-agent-secret"
        )
        
        # Target agent information
        target_agent_id = "target-agent-id"
        websocket_url = "wss://target-agent.example.com/ws"
        
        logger.info(f"Connecting to agent {target_agent_id}")
        
        try:
            # Connect to the target agent
            # The channel manager returns a channel implementing AgentChannelProtocol
            channel = await sdk.channels.connect_to_agent(
                target_agent_id=target_agent_id,
                channel_type="websocket",
                websocket_url=websocket_url
            )
            
            logger.info(f"Connected to agent {target_agent_id}")
            
            # Use the channel through the protocol interface
            await send_and_receive(channel, "Hello from WebSocket channel example!")
            
            # Close the connection
            await channel.close("example_complete")
            logger.info("Channel closed")
            
        except ConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
        except MessageError as e:
            logger.error(f"Message error: {str(e)}")
        except ChannelError as e:
            logger.error(f"Channel error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error initializing SDK: {str(e)}")
        
if __name__ == "__main__":
    asyncio.run(main()) 