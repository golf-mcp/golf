"""Channel module for agent communication."""

# Import protocol definitions
from .protocol import MessageType, ChannelState, AgentChannelProtocol

# Import channel utilities
from .utils import ChannelUtilities

# Import channel implementations
from .websocket import WebSocketChannel

# Import channel manager
from .manager import ChannelManager

# Import agent wrapper
from .agent import ChannelAgent

__all__ = [
    "MessageType",
    "ChannelState",
    "AgentChannelProtocol",
    "ChannelUtilities",
    "WebSocketChannel",
    "ChannelManager",
    "ChannelAgent"
] 