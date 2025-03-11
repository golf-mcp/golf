"""Base channel interface for agent communication."""

import abc
import uuid
from typing import Dict, Any, Optional

class AgentChannel(abc.ABC):
    """Abstract base class for all agent communication channels."""
    
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
        """Create a standard message envelope."""
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
        
    @abc.abstractmethod
    async def connect(self, target_agent_id: str) -> None:
        """Establish connection to target agent."""
        pass
        
    @abc.abstractmethod
    async def send_message(self, 
                          content_type: str, 
                          content_data: Dict[str, Any],
                          reply_to: Optional[str] = None) -> str:
        """Send message to connected agent.
        
        Returns:
            The message_id of the sent message
        """
        pass
        
    @abc.abstractmethod
    async def receive_message(self) -> Dict[str, Any]:
        """Receive message from connected agent."""
        pass
        
    @abc.abstractmethod
    async def close(self, reason: str = "normal") -> None:
        """Close the connection."""
        pass
        
    @property
    @abc.abstractmethod
    def is_connected(self) -> bool:
        """Check if channel is currently connected."""
        pass
        
    def _get_iso_timestamp(self) -> str:
        """Get current time as ISO 8601 string."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat() 