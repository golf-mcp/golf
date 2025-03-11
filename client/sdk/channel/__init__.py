"""Channel package for agent-to-agent communication."""

from .base import AgentChannel
from .protocol import MessageType
from .manager import ChannelManager

__all__ = [
    "AgentChannel",
    "MessageType",
    "ChannelManager"
] 