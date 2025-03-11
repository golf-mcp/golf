"""Base channel interface for agent communication."""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone

class AgentChannel:
    """Interface for agent communication channels.
    
    All channel implementations must implement these methods.
    """
    
    def __init__(self):
        self._channel_id = str(uuid.uuid4())
        self._sequence = 0
        
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
        """Create a standard message envelope.
        
        Args:
            content_type: Type of message to send
            content_data: Message data
            recipient_id: ID of the recipient agent
            sender_id: ID of the sender agent
            reply_to: Optional message ID to reply to
            
        Returns:
            A message envelope dictionary
        """
        return {
            "meta": {
                "message_id": str(uuid.uuid4()),
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "timestamp": self._get_iso_timestamp(),
                "sequence": self.next_sequence(),
                "channel_id": self.channel_id,
                "reply_to": reply_to
            },
            "content": {
                "type": content_type,
                "data": content_data
            }
        }
        
    async def connect(self, target_agent_id: str) -> None:
        """Establish connection to target agent.
        
        Args:
            target_agent_id: ID of the target agent to connect to
            
        Raises:
            ConnectionError: If connection fails
        """
        raise NotImplementedError("Subclasses must implement connect()")
        
    async def send_message(self, 
                          content_type: str, 
                          content_data: Dict[str, Any],
                          reply_to: Optional[str] = None) -> str:
        """Send message to connected agent.
        
        Args:
            content_type: Type of message to send
            content_data: Message data
            reply_to: Optional message ID to reply to
            
        Returns:
            The message_id of the sent message
            
        Raises:
            ConnectionError: If not connected
            MessageError: If sending fails
        """
        raise NotImplementedError("Subclasses must implement send_message()")
        
    async def receive_message(self) -> Dict[str, Any]:
        """Receive message from connected agent.
        
        Returns:
            The received message
            
        Raises:
            ConnectionError: If not connected
            MessageError: If receiving fails
        """
        raise NotImplementedError("Subclasses must implement receive_message()")
        
    async def close(self, reason: str = "normal") -> None:
        """Close the connection.
        
        Args:
            reason: Reason for closing the connection
        """
        raise NotImplementedError("Subclasses must implement close()")
        
    @property
    def is_connected(self) -> bool:
        """Check if channel is currently connected."""
        raise NotImplementedError("Subclasses must implement is_connected")
        
    def _get_iso_timestamp(self) -> str:
        """Get current time as ISO 8601 string."""
        return datetime.now(timezone.utc).isoformat() 