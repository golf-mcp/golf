"""Base utilities for agent communication channels."""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone

class ChannelUtilities:
    """Common utilities for agent communication channels.
    
    This class provides common functionality that can be used by channel
    implementations. It is not meant to be instantiated directly, but rather
    to be inherited from or composed with channel implementations.
    """
    
    def __init__(self):
        """Initialize with basic tracking attributes."""
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
        
    def _get_iso_timestamp(self) -> str:
        """Get current ISO 8601 timestamp with timezone."""
        return datetime.now(timezone.utc).isoformat() 