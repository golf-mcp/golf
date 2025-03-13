"""WebSocket implementation of agent channel."""

import json
import asyncio
import logging
import os
from typing import Dict, Any, Optional
import websockets
from uuid import UUID

from ..exceptions import ConnectionError, MessageError
from .utils import ChannelUtilities
from .protocol import MessageType, ChannelState

logger = logging.getLogger(__name__)

# Import message recorder only if in test mode
_TESTING = os.environ.get("AUTHED_TESTING", "0") == "1"
if _TESTING:
    try:
        from ..testing.test_agents.message_recorder import record_outgoing, record_incoming
        logger.info("Message recording enabled for WebSocketChannel")
    except ImportError:
        logger.warning("Message recorder not found, recording disabled")
        record_outgoing = record_incoming = lambda *args, **kwargs: None

class WebSocketChannel(ChannelUtilities):
    """WebSocket-based agent communication channel.
    
    Implements the AgentChannelProtocol using WebSocket as the transport.
    """
    
    def __init__(self, 
                agent_id: str = None, 
                auth_handler = None):
        """Initialize WebSocket channel.
        
        Args:
            agent_id: ID of this agent
            auth_handler: Authentication handler for token operations
        """
        super().__init__()
        self._agent_id = agent_id
        self._auth = auth_handler
        self.heartbeat_interval = 30
        self.ws_connection = None
        self._target_agent_id = None
        self._heartbeat_task = None
        self._state = ChannelState.DISCONNECTED
        self._message_queue = asyncio.Queue()
        self._receiver_task = None
        
    async def connect(self, target_agent_id: str, **kwargs) -> None:
        """Establish WebSocket connection to target agent.
        
        Args:
            target_agent_id: ID of the target agent
            **kwargs: Additional parameters:
                - websocket_url: WebSocket URL for the target agent (required)
                - heartbeat_interval: Seconds between heartbeat messages (optional)
        """
        # Extract parameters
        websocket_url = kwargs.get('websocket_url')
        if not websocket_url:
            raise ValueError("websocket_url is required for WebSocket connection")
            
        # Update heartbeat interval if provided
        if 'heartbeat_interval' in kwargs:
            self.heartbeat_interval = kwargs['heartbeat_interval']
            
        if self.is_connected:
            raise ConnectionError("Already connected to an agent")
            
        self._state = ChannelState.CONNECTING
        
        try:
            # Get interaction token from registry
            token = await self._auth.get_interaction_token(
                target_agent_id if isinstance(target_agent_id, UUID) else UUID(target_agent_id)
            )
            
            logger.debug(f"Connecting to WebSocket URL: {websocket_url}")
            
            try:
                # Connect with authentication
                headers = {"Authorization": f"Bearer {token}"}
                self.ws_connection = await websockets.connect(
                    websocket_url,
                    additional_headers=headers
                )
                
                self._target_agent_id = target_agent_id
                
                # Start message receiver task
                self._start_receiver()
                
                # Send channel open message
                await self.send_message(
                    MessageType.CHANNEL_OPEN,
                    {
                        "protocol_version": "1.0",
                        "capabilities": ["json"]
                    }
                )
                
                # Wait for channel accept message
                accept_message = await self._wait_for_message_type(MessageType.CHANNEL_ACCEPT, timeout=10)
                if not accept_message:
                    await self.close("accept_timeout")
                    raise ConnectionError("Timeout waiting for channel acceptance")
                
                self._state = ChannelState.CONNECTED
                
                # Start heartbeat if enabled
                if self.heartbeat_interval > 0:
                    self._start_heartbeat()
                    
                logger.info(f"Connected to agent {target_agent_id} via WebSocket")
                
            except Exception as e:
                logger.error(f"Failed to connect to agent {target_agent_id}: {str(e)}")
                self.ws_connection = None
                self._state = ChannelState.DISCONNECTED
                raise ConnectionError(f"Failed to connect: {str(e)}")
                
        except Exception as e:
            self._state = ChannelState.DISCONNECTED
            raise ConnectionError(f"Connection setup failed: {str(e)}")
            
    async def send_message(self, 
                          content_type: str, 
                          content_data: Dict[str, Any],
                          reply_to: Optional[str] = None) -> str:
        """Send message to connected agent."""
        if not self.is_connected and self._state != ChannelState.CONNECTING:
            logger.error(f"Cannot send message: state={self._state}, is_connected={self.is_connected}")
            raise ConnectionError("Not connected to agent")
            
        envelope = self.create_message_envelope(
            content_type,
            content_data,
            self._target_agent_id,
            self._agent_id,
            reply_to
        )
        
        try:
            # Record outgoing message if in test mode
            if _TESTING:
                record_outgoing(envelope, self._agent_id, self._target_agent_id)
                
            await self.ws_connection.send(json.dumps(envelope))
            return envelope["meta"]["message_id"]
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            raise MessageError(f"Failed to send message: {str(e)}")
            
    async def receive_message(self) -> Dict[str, Any]:
        """Receive message from connected agent."""
        if not self.is_connected:
            raise ConnectionError("Not connected to agent")
            
        try:
            # Get message from queue (populated by receiver task)
            message = await self._message_queue.get()
            self._message_queue.task_done()
            
            # Handle heartbeats internally
            if message["content"]["type"] == MessageType.HEARTBEAT:
                # Skip heartbeats and get next message
                return await self.receive_message()
                
            return message
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Failed to receive message: {str(e)}")
            raise MessageError(f"Failed to receive message: {str(e)}")
            
    async def close(self, reason: str = "normal") -> None:
        """Close the WebSocket connection."""
        if self._state != ChannelState.DISCONNECTED:
            self._state = ChannelState.CLOSING
            
            try:
                # Send close message if connection is still open
                if self.ws_connection and (hasattr(self.ws_connection, 'open') and self.ws_connection.open):
                    try:
                        await self.send_message(
                            MessageType.CHANNEL_CLOSE,
                            {"reason": reason}
                        )
                    except:
                        pass  # Best effort
                        
                # Stop tasks
                self._stop_heartbeat()
                self._stop_receiver()
                
                # Close connection
                if self.ws_connection:
                    await self.ws_connection.close()
                    logger.info(f"Closed connection to agent {self._target_agent_id}")
            except Exception as e:
                logger.error(f"Error closing connection: {str(e)}")
            finally:
                self.ws_connection = None
                self._target_agent_id = None
                self._state = ChannelState.DISCONNECTED
                
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        connection_open = (self.ws_connection is not None and 
                          (not hasattr(self.ws_connection, 'open') or self.ws_connection.open))
        return connection_open and self._state == ChannelState.CONNECTED
                
    def _start_heartbeat(self) -> None:
        """Start heartbeat task."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
    def _stop_heartbeat(self) -> None:
        """Stop heartbeat task."""
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
            
    def _start_receiver(self) -> None:
        """Start message receiver task."""
        if self._receiver_task is None:
            self._receiver_task = asyncio.create_task(self._receiver_loop())
            
    def _stop_receiver(self) -> None:
        """Stop message receiver task."""
        if self._receiver_task is not None:
            self._receiver_task.cancel()
            self._receiver_task = None
            
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        try:
            while self.is_connected:
                await asyncio.sleep(self.heartbeat_interval)
                if self.is_connected:
                    await self.send_message(MessageType.HEARTBEAT, {})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat error: {str(e)}")
            
    async def _receiver_loop(self) -> None:
        """Receive messages and put them in the queue."""
        try:
            while self.ws_connection and (not hasattr(self.ws_connection, 'open') or self.ws_connection.open):
                try:
                    data = await self.ws_connection.recv()
                    message = json.loads(data)
                    
                    # Validate message format
                    if "meta" not in message or "content" not in message:
                        logger.warning("Received invalid message format")
                        continue
                    
                    # Record incoming message if in test mode
                    if _TESTING:
                        sender_id = message.get("meta", {}).get("sender", "unknown")
                        record_incoming(message, sender_id, self._agent_id)
                        
                    # Put message in queue
                    await self._message_queue.put(message)
                    
                except websockets.exceptions.ConnectionClosed:
                    logger.info("WebSocket connection closed")
                    break
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON")
                except Exception as e:
                    logger.error(f"Error in receiver loop: {str(e)}")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Receiver task error: {str(e)}")
        finally:
            # If we exit the loop unexpectedly, close the channel
            if self._state not in [ChannelState.CLOSING, ChannelState.DISCONNECTED]:
                asyncio.create_task(self.close("receiver_error"))
                
    async def _wait_for_message_type(self, message_type: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Wait for a specific message type.
        
        Args:
            message_type: The message type to wait for
            timeout: Maximum time to wait in seconds
            
        Returns:
            The message if received, None if timed out
        """
        try:
            # Create a temporary queue for this wait operation
            temp_queue = asyncio.Queue()
            
            # Function to check messages
            async def check_messages():
                while True:
                    try:
                        message = await self._message_queue.get()
                        
                        # Check if this is the message we're waiting for
                        if message["content"]["type"] == message_type:
                            # Put it in our temp queue and stop
                            await temp_queue.put(message)
                            self._message_queue.task_done()
                            break
                            
                        # Otherwise, put it back in the main queue
                        await self._message_queue.put(message)
                        self._message_queue.task_done()
                        
                    except Exception as e:
                        logger.error(f"Error checking messages: {str(e)}")
                        break
            
            # Start checking messages
            task = asyncio.create_task(check_messages())
            
            # Wait for result or timeout
            try:
                return await asyncio.wait_for(temp_queue.get(), timeout)
            except asyncio.TimeoutError:
                return None
            finally:
                # Cancel the task if it's still running
                if not task.done():
                    task.cancel()
                    
        except Exception as e:
            logger.error(f"Error waiting for message: {str(e)}")
            return None 