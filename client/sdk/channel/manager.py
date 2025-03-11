"""Channel manager for agent communication."""

from typing import Dict
import logging
from .base import AgentChannel

logger = logging.getLogger(__name__)

class ChannelManager:
    """Manages agent communication channels."""
    
    def __init__(self, authed_sdk):
        """Initialize the channel manager.
        
        Args:
            authed_sdk: Reference to the Authed SDK instance
        """
        self.authed = authed_sdk
        self._active_channels: Dict[str, AgentChannel] = {}
        
    async def connect_to_agent(self, target_agent_id: str, websocket_url: str) -> AgentChannel:
        """Connect to another agent using WebSocket.
        
        Args:
            target_agent_id: ID of the target agent
            websocket_url: WebSocket URL for the target agent
            
        Returns:
            An established communication channel to the target agent
        """
        # Import here to avoid circular imports
        from .websocket import WebSocketChannel
        
        # Check if we already have an active channel
        channel_key = f"{self.authed.agent_id}:{target_agent_id}"
        if channel_key in self._active_channels and self._active_channels[channel_key].is_connected:
            logger.debug(f"Reusing existing channel to {target_agent_id}")
            return self._active_channels[channel_key]
            
        # Create new channel
        logger.debug(f"Creating new channel to {target_agent_id}")
        channel = WebSocketChannel(
            agent_id=self.authed.agent_id,
            auth_handler=self.authed.auth
        )
        
        await channel.connect(target_agent_id, websocket_url)
        
        # Store in active channels
        self._active_channels[channel_key] = channel
        return channel
        
    async def disconnect_from_agent(self, target_agent_id: str, reason: str = "normal") -> None:
        """Disconnect from an agent.
        
        Args:
            target_agent_id: ID of the target agent
            reason: Reason for disconnection
        """
        channel_key = f"{self.authed.agent_id}:{target_agent_id}"
        if channel_key in self._active_channels:
            logger.debug(f"Closing channel to {target_agent_id}")
            channel = self._active_channels[channel_key]
            await channel.close(reason)
            del self._active_channels[channel_key]
            
    def get_active_channels(self) -> Dict[str, AgentChannel]:
        """Get all active channels."""
        return {k: v for k, v in self._active_channels.items() if v.is_connected} 