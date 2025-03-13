"""Simplified agent wrapper for WebSocket channel communication.

This module provides a high-level wrapper around the Authed SDK's WebSocket
channel functionality, making it easy to set up agent communication with
minimal boilerplate.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timezone

from ..manager import Authed
from .protocol import MessageType
from ..server.websocket import WebSocketHandler

logger = logging.getLogger(__name__)

# Type for message handlers
MessageHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]

class Agent:
    """Simplified agent wrapper for WebSocket channel communication.
    
    This class provides a high-level interface for setting up an agent that can
    communicate with other agents via WebSocket channels.
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_secret: str,
        registry_url: str = "https://api.getauthed.dev",
        private_key: Optional[str] = None,
        public_key: Optional[str] = None,
        handlers: Optional[Dict[str, MessageHandler]] = None
    ):
        """Initialize the agent.
        
        Args:
            agent_id: ID of this agent
            agent_secret: Secret for this agent
            registry_url: URL of the registry service (default: production)
            private_key: Optional private key for this agent
            public_key: Optional public key for this agent
            handlers: Optional dictionary of message type to handler functions
        """
        self.agent_id = agent_id
        self.agent_secret = agent_secret
        self.registry_url = registry_url
        self.private_key = private_key
        self.public_key = public_key
        
        # Initialize the SDK
        self.sdk = Authed.initialize(
            registry_url=registry_url,
            agent_id=agent_id,
            agent_secret=agent_secret,
            private_key=private_key,
            public_key=public_key
        )
        
        # Create WebSocket handler
        self.ws_handler = WebSocketHandler(authed_sdk=self.sdk)
        
        # Register message handlers
        if handlers:
            for message_type, handler in handlers.items():
                self.register_handler(message_type, handler)
    
    def register_handler(self, message_type: str, handler: MessageHandler) -> None:
        """Register a handler for a specific message type.
        
        Args:
            message_type: Type of message to handle (e.g., MessageType.REQUEST)
            handler: Async function that takes a message and returns a response
        """
        self.ws_handler.register_handler(message_type, handler)
    
    async def connect_to_agent(
        self,
        target_agent_id: str,
        websocket_url: str,
        **kwargs
    ) -> Any:
        """Connect to another agent.
        
        Args:
            target_agent_id: ID of the target agent
            websocket_url: WebSocket URL of the target agent
            **kwargs: Additional parameters for the connection
            
        Returns:
            Channel object for communication
        """
        return await self.sdk.channels.connect_to_agent(
            target_agent_id=target_agent_id,
            channel_type="websocket",
            websocket_url=websocket_url,
            **kwargs
        )
    
    async def send_message(
        self,
        channel,
        content_type: str,
        content_data: Dict[str, Any],
        reply_to: Optional[str] = None
    ) -> str:
        """Send a message on a channel.
        
        Args:
            channel: Channel to send the message on
            content_type: Type of message to send
            content_data: Message content data
            reply_to: Optional message ID this is replying to
            
        Returns:
            ID of the sent message
        """
        return await channel.send_message(
            content_type=content_type,
            content_data=content_data,
            reply_to=reply_to
        )
    
    async def receive_message(
        self,
        channel,
        timeout: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """Receive a message on a channel with timeout.
        
        Args:
            channel: Channel to receive the message on
            timeout: Timeout in seconds
            
        Returns:
            Received message or None if timeout
            
        Raises:
            asyncio.TimeoutError: If no message is received within the timeout
        """
        return await asyncio.wait_for(
            channel.receive_message(),
            timeout=timeout
        )
    
    async def close_channel(
        self,
        channel,
        reason: str = "normal"
    ) -> None:
        """Close a channel.
        
        Args:
            channel: Channel to close
            reason: Reason for closing the channel
        """
        await channel.close(reason)
    
    async def send_and_receive(
        self,
        target_agent_id: str,
        websocket_url: str,
        content_type: str,
        content_data: Dict[str, Any],
        timeout: float = 10.0,
        auto_close: bool = True
    ) -> Dict[str, Any]:
        """Send a message to an agent and wait for a response.
        
        This is a convenience method that combines connect, send, receive, and close.
        
        Args:
            target_agent_id: ID of the target agent
            websocket_url: WebSocket URL of the target agent
            content_type: Type of message to send
            content_data: Message content data
            timeout: Timeout in seconds for receiving the response
            auto_close: Whether to automatically close the channel after receiving
            
        Returns:
            Response message
            
        Raises:
            ConnectionError: If connection fails
            TimeoutError: If no response is received within the timeout
        """
        # Connect to the agent
        channel = await self.connect_to_agent(
            target_agent_id=target_agent_id,
            websocket_url=websocket_url
        )
        
        try:
            # Send the message
            await self.send_message(
                channel=channel,
                content_type=content_type,
                content_data=content_data
            )
            
            # Wait for a response
            response = await self.receive_message(
                channel=channel,
                timeout=timeout
            )
            
            return response
        finally:
            # Close the channel if auto_close is True
            if auto_close:
                await self.close_channel(channel, "send_and_receive_complete")
    
    async def send_text_message(
        self,
        target_agent_id: str,
        websocket_url: str,
        text: str,
        timeout: float = 10.0,
        auto_close: bool = True
    ) -> Dict[str, Any]:
        """Send a simple text message to an agent and wait for a response.
        
        This is a convenience method for sending text messages.
        
        Args:
            target_agent_id: ID of the target agent
            websocket_url: WebSocket URL of the target agent
            text: Text message to send
            timeout: Timeout in seconds for receiving the response
            auto_close: Whether to automatically close the channel after receiving
            
        Returns:
            Response message
        """
        # Create message content
        content_data = {
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Send and receive
        return await self.send_and_receive(
            target_agent_id=target_agent_id,
            websocket_url=websocket_url,
            content_type=MessageType.REQUEST,
            content_data=content_data,
            timeout=timeout,
            auto_close=auto_close
        )
    
    def get_iso_timestamp(self) -> str:
        """Get current ISO 8601 timestamp with timezone.
        
        Returns:
            ISO 8601 formatted timestamp
        """
        return datetime.now(timezone.utc).isoformat()
    
    async def handle_websocket(self, websocket, path: str) -> None:
        """Handle a WebSocket connection.
        
        This method should be called from a WebSocket endpoint handler.
        
        Args:
            websocket: WebSocket connection object
            path: Path of the WebSocket endpoint
        """
        await self.ws_handler.handle_connection(websocket, path)
    
    @staticmethod
    def create_text_message_handler(
        response_prefix: str = "Received: "
    ) -> MessageHandler:
        """Create a simple text message handler.
        
        This is a convenience method for creating a handler for text messages.
        
        Args:
            response_prefix: Prefix to add to the response text
            
        Returns:
            Message handler function
        """
        async def handle_text_message(message: Dict[str, Any]) -> Dict[str, Any]:
            # Extract message content
            content_data = message["content"]["data"]
            text = content_data.get("text", "No text provided")
            
            # Create response
            response_data = {
                "text": f"{response_prefix}{text}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            return {
                "type": MessageType.RESPONSE,
                "data": response_data
            }
        
        return handle_text_message