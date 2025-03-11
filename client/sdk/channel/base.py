"""Base channel interface for agent communication."""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone

class AgentChannel:
    """Interface for agent communication channels.
    
    This class defines the interface that all channel implementations must follow.
    It provides:
    1. Common functionality (message envelope creation, sequence tracking)
    2. Default implementations that can be overridden by subclasses
    3. Connection state tracking
    
    Subclasses should override methods like connect(), send_message(), 
    receive_message(), and close() with their specific implementations.
    """
    
    def __init__(self):
        """Initialize the channel with basic tracking attributes."""
        self._channel_id = str(uuid.uuid4())
        self._sequence = 0
        self._connected = False
        
    @property
    def channel_id(self) -> str:
        """Get the unique channel identifier."""
        return self._channel_id
        
    def next_sequence(self) -> int:
        """Get the next message sequence number."""
        self._sequence += 1
        return self._sequence
        
    def create_message_envelope(self, 
                               content_type: str, 
                               content_data: Dict[str, Any],
                               recipient_id: str,
                               sender_id: str,
                               reply_to: Optional[str] = None) -> Dict[str, Any]:
        """Create a message envelope.
        
        Args:
            content_type: Type of message content
            content_data: Message content data
            recipient_id: ID of the recipient agent
            sender_id: ID of the sender agent
            reply_to: Optional message ID this is replying to
            
        Returns:
            Message envelope dictionary
        """
        message_id = str(uuid.uuid4())
        
        return {
            "meta": {
                "message_id": message_id,
                "channel_id": self.channel_id,
                "sequence": self.next_sequence(),
                "timestamp": self._get_iso_timestamp(),
                "sender": sender_id,
                "recipient": recipient_id,
                "reply_to": reply_to
            },
            "content": {
                "type": content_type,
                "data": content_data
            }
        }
        
    async def connect(self, target_agent_id: str, **kwargs) -> None:
        """Connect to a target agent.
        
        This is a base implementation that subclasses should override
        with their specific connection logic.
        
        Args:
            target_agent_id: ID of the target agent
            **kwargs: Additional connection parameters specific to the channel type
        """
        # Base implementation just tracks connection state
        # Subclasses should override with actual connection logic
        self._connected = True
        
    async def send_message(self, 
                          content_type: str, 
                          content_data: Dict[str, Any],
                          reply_to: Optional[str] = None) -> str:
        """Send a message to the connected agent.
        
        This is a base implementation that subclasses should override
        with their specific message sending logic.
        
        Args:
            content_type: Type of message content
            content_data: Message content data
            reply_to: Optional message ID this is replying to
            
        Returns:
            Message ID of the sent message
        """
        # Base implementation just checks connection state
        # Subclasses should override with actual message sending logic
        if not self.is_connected:
            raise ConnectionError("Not connected to agent")
        return str(uuid.uuid4())  # Placeholder message ID
        
    async def receive_message(self) -> Dict[str, Any]:
        """Receive a message from the connected agent.
        
        This is a base implementation that subclasses should override
        with their specific message receiving logic.
        
        Returns:
            Received message envelope
        """
        # Base implementation just checks connection state
        # Subclasses should override with actual message receiving logic
        if not self.is_connected:
            raise ConnectionError("Not connected to agent")
        return {}  # Placeholder empty message
        
    async def close(self, reason: str = "normal") -> None:
        """Close the connection to the agent.
        
        This is a base implementation that subclasses should override
        with their specific connection closing logic.
        
        Args:
            reason: Reason for closing the connection
        """
        # Base implementation just updates connection state
        # Subclasses should override with actual connection closing logic
        self._connected = False
        
    @property
    def is_connected(self) -> bool:
        """Check if connected to an agent.
        
        Subclasses may override this with more specific connection state checking.
        
        Returns:
            True if connected, False otherwise
        """
        return self._connected
        
    def _get_iso_timestamp(self) -> str:
        """Get current ISO 8601 timestamp with timezone."""
        return datetime.now(timezone.utc).isoformat() 