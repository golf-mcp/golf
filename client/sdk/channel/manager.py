"""Manager for agent communication channels."""

import logging
from typing import Dict, Optional
from uuid import UUID

from .protocol import AgentChannelProtocol
from .websocket import WebSocketChannel
from ..exceptions import ChannelError

logger = logging.getLogger(__name__)

class ChannelManager:
    """Manages agent communication channels."""
    
    def __init__(self, agent_id: str, auth_handler):
        """Initialize channel manager.
        
        Args:
            agent_id: ID of this agent
            auth_handler: Authentication handler for token operations
        """
        self._agent_id = agent_id
        self._auth_handler = auth_handler
        self._active_channels: Dict[str, AgentChannelProtocol] = {}
        self._websocket_urls: Dict[str, str] = {}
        
    async def connect_to_agent(self, 
                              target_agent_id: str, 
                              channel_type: str = "websocket",
                              **kwargs) -> AgentChannelProtocol:
        """Connect to an agent using the specified channel type.
        
        Args:
            target_agent_id: ID of the target agent
            channel_type: Type of channel to use (default: websocket)
            **kwargs: Additional parameters for the channel:
                - websocket_url: WebSocket URL for the target agent (required for websocket)
                - heartbeat_interval: Seconds between heartbeat messages (optional)
                
        Returns:
            Connected agent channel
            
        Raises:
            ChannelError: If the channel type is not supported or connection fails
        """
        # Normalize UUID to string
        if isinstance(target_agent_id, UUID):
            target_agent_id = str(target_agent_id)
            
        # Check if we already have an active channel
        if target_agent_id in self._active_channels:
            channel = self._active_channels[target_agent_id]
            if channel.is_connected:
                logger.debug(f"Reusing existing channel to agent {target_agent_id}")
                return channel
            else:
                # Channel exists but is disconnected, remove it
                logger.debug(f"Removing disconnected channel to agent {target_agent_id}")
                await self.disconnect_from_agent(target_agent_id)
                
        # Create a new channel
        if channel_type == "websocket":
            # Store the websocket URL for future reconnections
            if 'websocket_url' in kwargs:
                self._websocket_urls[target_agent_id] = kwargs['websocket_url']
                
            # Create and connect the channel
            channel = WebSocketChannel(
                agent_id=self._agent_id,
                auth_handler=self._auth_handler
            )
            
            # Connect to the agent
            await channel.connect(target_agent_id, **kwargs)
            
            # Store the channel
            self._active_channels[target_agent_id] = channel
            return channel
        else:
            raise ChannelError(f"Unsupported channel type: {channel_type}")
            
    async def disconnect_from_agent(self, target_agent_id: str) -> None:
        """Disconnect from an agent.
        
        Args:
            target_agent_id: ID of the target agent
        """
        # Normalize UUID to string
        if isinstance(target_agent_id, UUID):
            target_agent_id = str(target_agent_id)
            
        if target_agent_id in self._active_channels:
            channel = self._active_channels[target_agent_id]
            try:
                await channel.close()
            except Exception as e:
                logger.error(f"Error closing channel to agent {target_agent_id}: {str(e)}")
            finally:
                del self._active_channels[target_agent_id]
                
    def get_channel(self, target_agent_id: str) -> Optional[AgentChannelProtocol]:
        """Get the channel for an agent.
        
        Args:
            target_agent_id: ID of the target agent
            
        Returns:
            Agent channel if connected, None otherwise
        """
        # Normalize UUID to string
        if isinstance(target_agent_id, UUID):
            target_agent_id = str(target_agent_id)
            
        if target_agent_id in self._active_channels:
            channel = self._active_channels[target_agent_id]
            if channel.is_connected:
                return channel
        return None
        
    async def disconnect_all(self) -> None:
        """Disconnect from all agents."""
        for agent_id in list(self._active_channels.keys()):
            await self.disconnect_from_agent(agent_id)
            
    def get_websocket_url(self, target_agent_id: str) -> Optional[str]:
        """Get the stored WebSocket URL for an agent.
        
        Args:
            target_agent_id: ID of the target agent
            
        Returns:
            WebSocket URL if stored, None otherwise
        """
        # Normalize UUID to string
        if isinstance(target_agent_id, UUID):
            target_agent_id = str(target_agent_id)
            
        return self._websocket_urls.get(target_agent_id) 