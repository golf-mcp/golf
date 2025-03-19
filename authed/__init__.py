"""Agent Authentication Client Package."""

__version__ = "0.2.3"

# Import the main classes for easy access
from authed.sdk import Authed
from authed.sdk.channel import Channel
from authed.sdk.channel.protocol import MessageType

# Expose these classes at the top level
__all__ = [
    "Authed",
    "Channel",
    "MessageType"
] 