"""WebSocket server handler for agent communication."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Awaitable, Optional
import websockets

from ..channel.protocol import MessageType
from ..exceptions import AuthenticationError

logger = logging.getLogger(__name__)

class WebSocketHandler:
    """Handler for incoming WebSocket connections."""
    
    def __init__(self, authed_sdk):
        """Initialize WebSocket handler.
        
        Args:
            authed_sdk: Reference to the Authed SDK instance
        """
        self.authed = authed_sdk
        self.message_handlers = {}
        self.active_connections = {}  # Map of channel_id to connection info
        
    def register_handler(self, 
                        message_type: str, 
                        handler: Callable[[Dict[str, Any]], Awaitable[Optional[Dict[str, Any]]]]):
        """Register a handler for a specific message type.
        
        Args:
            message_type: The message type to handle
            handler: Async function that takes a message and returns an optional response
        """
        self.message_handlers[message_type] = handler
        
    async def handle_connection(self, websocket, path):
        """Handle an incoming WebSocket connection."""
        # Authenticate the connection
        auth_header = websocket.request_headers.get('Authorization')
        if not auth_header:
            await websocket.close(1008, "Missing authentication")
            return
            
        # Verify token with registry
        token = auth_header.replace('Bearer ', '')
        try:
            is_valid = await self.authed.auth.verify_token(token)
            if not is_valid:
                await websocket.close(1008, "Invalid authentication")
                return
        except AuthenticationError as e:
            logger.error(f"Authentication error: {str(e)}")
            await websocket.close(1008, "Authentication error")
            return
            
        # Connection info
        connection_info = {
            "websocket": websocket,
            "remote_addr": websocket.remote_address,
            "connected_at": datetime.now(timezone.utc),
            "agent_id": None,  # Will be set when we receive the first message
            "channel_id": None  # Will be set when we receive channel.open
        }
        
        try:
            async for message_data in websocket:
                try:
                    # Parse message
                    message = json.loads(message_data)
                    
                    # Validate message format
                    if "meta" not in message or "content" not in message:
                        await self._send_error(websocket, "Invalid message format")
                        continue
                        
                    # Get content type
                    content_type = message["content"]["type"]
                    
                    # Handle channel management messages
                    if content_type == MessageType.CHANNEL_OPEN:
                        await self._handle_channel_open(websocket, message)
                        connection_info["agent_id"] = message["meta"]["sender_id"]
                        connection_info["channel_id"] = message["meta"]["channel_id"]
                        self.active_connections[message["meta"]["channel_id"]] = connection_info
                        continue
                    elif content_type == MessageType.CHANNEL_CLOSE:
                        await self._handle_channel_close(websocket, message)
                        continue
                    elif content_type == MessageType.HEARTBEAT:
                        # Respond to heartbeats
                        response = {
                            "meta": {
                                "message_id": str(uuid.uuid4()),
                                "sender_id": self.authed.agent_id,
                                "recipient_id": message["meta"]["sender_id"],
                                "timestamp": self._get_iso_timestamp(),
                                "sequence": 0,
                                "channel_id": message["meta"]["channel_id"],
                                "reply_to": message["meta"]["message_id"]
                            },
                            "content": {
                                "type": MessageType.HEARTBEAT,
                                "data": {}
                            }
                        }
                        await websocket.send(json.dumps(response))
                        continue
                        
                    # Dispatch to registered handler
                    if content_type in self.message_handlers:
                        response_data = await self.message_handlers[content_type](message)
                        if response_data:
                            await websocket.send(json.dumps(response_data))
                    else:
                        await self._send_error(
                            websocket, 
                            f"Unsupported message type: {content_type}",
                            message["meta"]["message_id"]
                        )
                        
                except json.JSONDecodeError:
                    await self._send_error(websocket, "Invalid JSON")
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    await self._send_error(websocket, f"Internal error: {str(e)}")
                    
        except websockets.exceptions.ConnectionClosed:
            # Clean up connection
            if connection_info["channel_id"]:
                self.active_connections.pop(connection_info["channel_id"], None)
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"WebSocket handler error: {str(e)}")
            
    async def _handle_channel_open(self, websocket, message):
        """Handle channel open request."""
        # Create response
        response = {
            "meta": {
                "message_id": str(uuid.uuid4()),
                "sender_id": self.authed.agent_id,
                "recipient_id": message["meta"]["sender_id"],
                "timestamp": self._get_iso_timestamp(),
                "sequence": 1,
                "channel_id": message["meta"]["channel_id"],
                "reply_to": message["meta"]["message_id"]
            },
            "content": {
                "type": MessageType.CHANNEL_ACCEPT,
                "data": {
                    "protocol_version": "1.0",
                    "capabilities": ["json"]
                }
            }
        }
        
        await websocket.send(json.dumps(response))
        
    async def _handle_channel_close(self, websocket, message):
        """Handle channel close request."""
        # Extract information
        channel_id = message["meta"]["channel_id"]
        sender_id = message["meta"]["sender_id"]
        reason = message["content"]["data"].get("reason", "normal")
        
        # Log the close event
        logger.info(f"Channel {channel_id} close requested by {sender_id} with reason: {reason}")
        
        # Send acknowledgment
        response = {
            "meta": {
                "message_id": str(uuid.uuid4()),
                "sender_id": self.authed.agent_id,
                "recipient_id": sender_id,
                "timestamp": self._get_iso_timestamp(),
                "sequence": 1,
                "channel_id": channel_id,
                "reply_to": message["meta"]["message_id"]
            },
            "content": {
                "type": MessageType.CHANNEL_CLOSE,
                "data": {
                    "acknowledged": True,
                    "reason": reason
                }
            }
        }
        
        try:
            await websocket.send(json.dumps(response))
            logger.debug(f"Sent close acknowledgment for channel {channel_id}")
        except Exception as e:
            logger.warning(f"Failed to send close acknowledgment: {str(e)}")
        
        # The connection will be closed after this method returns
        
    async def _send_error(self, websocket, error_message, reply_to=None, sender_id=None):
        """Send an error message.
        
        Args:
            websocket: The WebSocket connection
            error_message: The error message to send
            reply_to: Optional message ID to reply to
            sender_id: Optional sender ID if known
        """
        error = {
            "meta": {
                "message_id": str(uuid.uuid4()),
                "sender_id": self.authed.agent_id,
                "recipient_id": sender_id or "anonymous",  # Use sender_id if available
                "timestamp": self._get_iso_timestamp(),
                "sequence": 0,
                "channel_id": "error",
                "reply_to": reply_to
            },
            "content": {
                "type": MessageType.ERROR,
                "data": {
                    "message": error_message
                }
            }
        }
        
        await websocket.send(json.dumps(error))
        
    def _get_iso_timestamp(self):
        """Get current time as ISO 8601 string."""
        return datetime.now(timezone.utc).isoformat() 