"""Simplified channel wrapper for WebSocket communication.

This module provides a high-level wrapper around the Authed SDK's WebSocket
channel functionality, making it easy to set up agent communication with
minimal boilerplate.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Awaitable, ClassVar
from datetime import datetime, timezone

# Import WebSocketHandler directly to avoid circular import
from ..server.websocket import WebSocketHandler
from .protocol import MessageType

logger = logging.getLogger(__name__)

# Type for message handlers
MessageHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]

class Channel:
    """Simplified channel wrapper for WebSocket communication.
    
    This class provides a high-level interface for setting up a channel that can
    communicate with other agents via WebSocket connections.
    
    The Channel uses a persistent Authed instance to maintain connections
    across multiple operations, ensuring that channels remain active even when
    the agent is processing messages or calling other tools.
    """
    
    # Class variable to store Authed instances by registry URL and agent ID
    _authed_instances: ClassVar[Dict[str, Any]] = {}
    
    def __init__(
        self,
        agent_id: str = None,
        agent_secret: str = None,
        registry_url: str = "https://api.getauthed.dev",
        private_key: Optional[str] = None,
        public_key: Optional[str] = None,
        handlers: Optional[Dict[str, MessageHandler]] = None,
        authed_sdk: Optional[Any] = None
    ):
        """Initialize the channel.
        
        Args:
            agent_id: ID of this agent (required if authed_sdk not provided)
            agent_secret: Secret for this agent (required if authed_sdk not provided)
            registry_url: URL of the registry service (default: production)
            private_key: Optional private key for this agent
            public_key: Optional public key for this agent
            handlers: Optional dictionary of message type to handler functions
            authed_sdk: Optional existing Authed SDK instance to use
        """
        self.registry_url = registry_url
        
        # Set up the SDK instance
        if authed_sdk:
            # Use the provided SDK instance
            logger.debug("Using provided Authed instance")
            self.sdk = authed_sdk
            self.agent_id = self.sdk.agent_id
            self.agent_secret = None  # Don't store the secret if using existing instance
            self.private_key = None   # Don't store the keys if using existing instance
            self.public_key = None
        else:
            # Validate required parameters
            if not agent_id or not agent_secret:
                raise ValueError("agent_id and agent_secret are required when authed_sdk is not provided")
                
            self.agent_id = agent_id
            self.agent_secret = agent_secret
            self.private_key = private_key
            self.public_key = public_key
            
            # Import Authed here to avoid circular import
            from ..manager import Authed
            
            # Create a unique key for this agent's Authed instance
            instance_key = f"{registry_url}:{agent_id}"
            
            # Check if we already have an Authed instance for this agent
            if instance_key in self._authed_instances:
                logger.debug(f"Reusing existing Authed instance for agent {agent_id}")
                self.sdk = self._authed_instances[instance_key]
            else:
                # Initialize a new SDK instance
                logger.debug(f"Creating new Authed instance for agent {agent_id}")
                self.sdk = Authed.initialize(
                    registry_url=registry_url,
                    agent_id=agent_id,
                    agent_secret=agent_secret,
                    private_key=private_key,
                    public_key=public_key
                )
                # Store the instance for future use
                self._authed_instances[instance_key] = self.sdk
        
        # Create WebSocket handler
        self.ws_handler = WebSocketHandler(authed_sdk=self.sdk)
        
        # Dictionary to store active channels
        self._channels: Dict[str, Any] = {}
        
        # Register default text message handler if none is provided for REQUEST type
        if not handlers or MessageType.REQUEST not in handlers:
            default_handler = self.create_text_message_handler()
            if not handlers:
                handlers = {MessageType.REQUEST: default_handler}
            else:
                handlers[MessageType.REQUEST] = default_handler
            logger.debug("Registered default text message handler")
        
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
    
    async def open_channel(
        self,
        target_agent_id: str,
        websocket_url: str,
        **kwargs
    ) -> Any:
        """Open a channel to another agent.
        
        Args:
            target_agent_id: ID of the target agent
            websocket_url: WebSocket URL of the target agent
            **kwargs: Additional parameters for the connection
            
        Returns:
            Channel object for communication
        """
        # Create a channel key
        channel_key = f"{target_agent_id}:{websocket_url}"
        
        # Check if we already have this channel
        if channel_key in self._channels:
            channel = self._channels[channel_key]
            if channel.is_connected:
                logger.debug(f"Reusing existing channel to {target_agent_id}")
                return channel
            else:
                logger.debug(f"Existing channel to {target_agent_id} is disconnected")
                # Remove the disconnected channel
                del self._channels[channel_key]
        
        # Connect to the agent
        logger.debug(f"Opening new channel to {target_agent_id}")
        channel = await self.sdk.channels.connect_to_agent(
            target_agent_id=target_agent_id,
            channel_type="websocket",
            websocket_url=websocket_url,
            **kwargs
        )
        
        # Store the channel
        self._channels[channel_key] = channel
        
        return channel
    
    def get_channel(self, target_agent_id: str, websocket_url: str) -> Optional[Any]:
        """Get an existing channel if it exists.
        
        Args:
            target_agent_id: ID of the target agent
            websocket_url: WebSocket URL of the target agent
            
        Returns:
            Channel object or None if not found
        """
        channel_key = f"{target_agent_id}:{websocket_url}"
        channel = self._channels.get(channel_key)
        
        if channel and channel.is_connected:
            return channel
        
        return None
    
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
        if not content_data.get("timestamp"):
            content_data["timestamp"] = self.get_iso_timestamp()
            
        return await channel.send_message(
            content_type=content_type,
            content_data=content_data,
            reply_to=reply_to
        )
    
    async def receive_message(
        self,
        channel,
        timeout: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Receive a message on a channel.
        
        Args:
            channel: Channel to receive the message on
            timeout: Optional timeout in seconds (None for no timeout)
            
        Returns:
            Received message or None if timeout
            
        Raises:
            asyncio.TimeoutError: If no message is received within the timeout
        """
        if timeout is not None:
            return await asyncio.wait_for(
                channel.receive_message(),
                timeout=timeout
            )
        else:
            return await channel.receive_message()
    
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
        # Remove from channels dict
        for key, value in list(self._channels.items()):
            if value == channel:
                del self._channels[key]
                break
                
        await channel.close(reason)
    
    async def close_all_channels(self, reason: str = "agent_shutdown") -> None:
        """Close all open channels.
        
        Args:
            reason: Reason for closing the channels
        """
        for channel in list(self._channels.values()):
            try:
                await channel.close(reason)
            except Exception as e:
                logger.error(f"Error closing channel: {e}")
        
        self._channels.clear()
    
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
    def create_text_message_handler() -> MessageHandler:
        """Create a simple text message handler.
        
        This handler echoes back the received text message.
        
        Returns:
            Message handler function
        """
        async def handle_text_message(message: Dict[str, Any]) -> Dict[str, Any]:
            # Extract text from the message
            content_data = message["content"]["data"]
            text = content_data.get("text", "")
            
            # Create a simple echo response
            response_data = {
                "text": text,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            return {
                "type": MessageType.RESPONSE,
                "data": response_data
            }
        
        return handle_text_message
    
    @classmethod
    def from_authed(
        cls,
        authed_sdk: Any,
        handlers: Optional[Dict[str, MessageHandler]] = None
    ) -> "Channel":
        """Create a Channel from an existing Authed instance.
        
        This is a convenience method for creating a Channel from an existing
        Authed instance.
        
        Args:
            authed_sdk: Existing Authed SDK instance
            handlers: Optional dictionary of message type to handler functions
            
        Returns:
            Channel instance
        """
        return cls(
            authed_sdk=authed_sdk,
            handlers=handlers
        )