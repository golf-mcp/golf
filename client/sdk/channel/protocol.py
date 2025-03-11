"""Protocol constants and utilities for agent channels."""

class MessageType:
    """Standard message types for channel protocol."""
    
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
    """Channel state constants."""
    
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing" 