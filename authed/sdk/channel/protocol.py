"""Protocol definitions for agent communication."""

from typing import Protocol, Dict, Any, Optional

# Message types
class MessageType:
    """Standard message types for agent communication."""
    
    # Channel management
    CHANNEL_OPEN = "channel.open"
    CHANNEL_ACCEPT = "channel.accept"
    CHANNEL_REJECT = "channel.reject"
    CHANNEL_CLOSE = "channel.close"
    HEARTBEAT = "channel.heartbeat"
    
    # Error handling
    ERROR = "error"
    
    # Application messages (examples)
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    
class ChannelState:
    """States for agent communication channels."""
    
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing"

class AgentChannelProtocol(Protocol):
    """Protocol defining the interface for agent communication channels.
    
    This Protocol defines the methods that all channel implementations
    must provide. Any class that implements these methods is considered
    a valid AgentChannel, regardless of inheritance.
    """
    
    @property
    def channel_id(self) -> str:
        """Get the unique channel identifier."""
        ...
    
    def create_message_envelope(self, 
                               content_type: str, 
                               content_data: Dict[str, Any],
                               recipient_id: str,
                               sender_id: str,
                               reply_to: Optional[str] = None) -> Dict[str, Any]:
        """Create a message envelope."""
        ...
    
    async def connect(self, target_agent_id: str, **kwargs) -> None:
        """Connect to a target agent."""
        ...
    
    async def send_message(self, 
                          content_type: str, 
                          content_data: Dict[str, Any],
                          reply_to: Optional[str] = None) -> str:
        """Send a message to the connected agent."""
        ...
    
    async def receive_message(self) -> Dict[str, Any]:
        """Receive a message from the connected agent."""
        ...
    
    async def close(self, reason: str = "normal") -> None:
        """Close the connection to the agent."""
        ...
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to an agent."""
        ... 