"""WebSocket server handler for agent communication."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Awaitable, Optional
import websockets

from ..channel.protocol import MessageType
from ..exceptions import AuthenticationError

logger = logging.getLogger(__name__)

# Import message recorder only if in test mode
_TESTING = os.environ.get("AUTHED_TESTING", "0") == "1"
if _TESTING:
    try:
        from ..testing.test_agents.message_recorder import record_outgoing, record_incoming
        logger.info("Message recording enabled for WebSocketHandler")
    except ImportError:
        logger.warning("Message recorder not found, recording disabled")
        record_outgoing = record_incoming = lambda *args, **kwargs: None

class WebSocketHandler:
    """Handler for incoming WebSocket connections."""
    
    def __init__(self, authed_sdk):
        """Initialize WebSocket handler.
        
        Args:
            authed_sdk: Reference to the Authed SDK instance
        """
        self.authed = authed_sdk
        self.message_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Optional[Dict[str, Any]]]]] = {}
        self.active_connections: Dict[str, Dict[str, Any]] = {}  # Map of channel_id to connection info
        
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
        # Connection info
        connection_info = {
            "websocket": websocket,
            "remote_addr": getattr(websocket, 'remote_address', ('unknown', 0)),
            "connected_at": datetime.now(timezone.utc),
            "agent_id": None,  # Will be set when we receive the first message
            "channel_id": None  # Will be set when we receive channel.open
        }
        
        # Authenticate the connection
        # For FastAPI WebSocket, headers are in websocket.headers
        # For standard websockets, headers are in websocket.request_headers
        # Handle different header formats
        headers = {}
        if hasattr(websocket, 'headers'):
            # FastAPI WebSocket
            headers = websocket.headers
        elif hasattr(websocket, 'request_headers'):
            # Standard websockets
            headers = websocket.request_headers
            
        # Extract Authorization header
        auth_header = None
        if isinstance(headers, dict):
            auth_header = headers.get('Authorization')
        elif hasattr(headers, 'get'):
            auth_header = headers.get('Authorization')
        else:
            # Try to iterate through headers if it's a list of tuples
            try:
                for key, value in headers:
                    if key.lower() == 'authorization':
                        auth_header = value
                        break
            except:
                logger.warning("Could not extract headers from WebSocket connection")
                
        if not auth_header:
            await websocket.close(1008, "Missing authentication")
            return
            
        # Verify token with registry
        token = auth_header.replace('Bearer ', '')
        try:
            # Check if verify_token method exists
            if hasattr(self.authed.auth, 'verify_token'):
                is_valid = await self.authed.auth.verify_token(token)
            else:
                # Fallback to a simple check if method doesn't exist
                # This should be replaced with proper verification
                logger.warning("verify_token method not found, using simple validation")
                is_valid = bool(token)
                
            if not is_valid:
                await websocket.close(1008, "Invalid authentication")
                return
        except AuthenticationError as e:
            logger.error(f"Authentication error: {str(e)}")
            await websocket.close(1008, "Authentication error")
            return
            
        # Handle messages
        try:
            # Check if websocket is a FastAPI WebSocket or a standard websockets WebSocket
            if hasattr(websocket, 'receive_json'):
                # FastAPI WebSocket
                while True:
                    try:
                        # Parse message
                        message_data = await websocket.receive_text()
                        message = json.loads(message_data)
                        
                        # Process message
                        await self._process_message(websocket, message, connection_info)
                    except json.JSONDecodeError:
                        await self._send_error(websocket, "Invalid JSON")
                    except RuntimeError as e:
                        # Handle WebSocket disconnection
                        if "Cannot call" in str(e) and "disconnect message" in str(e):
                            logger.info("WebSocket client disconnected")
                            break
                        else:
                            logger.error(f"WebSocket runtime error: {str(e)}")
                            break
                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")
                        try:
                            await self._send_error(websocket, f"Internal error: {str(e)}")
                        except Exception:
                            # If sending the error fails, just log it and continue
                            logger.error("Failed to send error message after processing error")
                            break
            else:
                # Standard websockets WebSocket
                async for message_data in websocket:
                    try:
                        # Parse message
                        message = json.loads(message_data)
                        
                        # Process message
                        await self._process_message(websocket, message, connection_info)
                    except json.JSONDecodeError:
                        await self._send_error(websocket, "Invalid JSON")
                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")
                        try:
                            await self._send_error(websocket, f"Internal error: {str(e)}")
                        except Exception:
                            # If sending the error fails, just log it and continue
                            logger.error("Failed to send error message after processing error")
                            break
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"WebSocket handler error: {str(e)}")
        finally:
            # Clean up connection
            if connection_info["channel_id"]:
                self.active_connections.pop(connection_info["channel_id"], None)
                logger.info(f"Removed channel {connection_info['channel_id']} from active connections")
                
    async def _process_message(self, websocket, message, connection_info):
        """Process a received message."""
        # Debug log the message structure
        logger.debug(f"Received message: {json.dumps(message, indent=2)}")
        
        # Record incoming message if in test mode
        if _TESTING:
            sender_id = message.get("meta", {}).get("sender_id", message.get("meta", {}).get("sender", "unknown"))
            record_incoming(message, sender_id, self.authed.agent_id)
        
        try:
            # Validate message format
            if "meta" not in message or "content" not in message:
                await self._send_error(websocket, "Invalid message format")
                return
            
            # Update connection info when we get sender info
            # Handle both 'sender_id' and 'sender' fields for compatibility
            meta = message.get("meta", {})
            sender_id = meta.get("sender_id", meta.get("sender", "anonymous"))
            if sender_id:
                connection_info["agent_id"] = sender_id
                
            # Get content type
            if "content" in message and "type" in message["content"]:
                content_type = message["content"]["type"]
            else:
                await self._send_error(websocket, "Invalid message content", None, sender_id)
                return
            
            # Handle channel management messages
            if content_type == MessageType.CHANNEL_OPEN:
                # Update connection info
                channel_id = meta.get("channel_id")
                if channel_id:
                    connection_info["channel_id"] = channel_id
                    self.active_connections[channel_id] = connection_info
                    
                    await self._handle_channel_open(websocket, message)
                else:
                    await self._send_error(websocket, "Missing channel_id in message", None, sender_id)
                return
            elif content_type == MessageType.CHANNEL_CLOSE:
                await self._handle_channel_close(websocket, message)
                # Connection will be closed after this
                return
            elif content_type == MessageType.HEARTBEAT:
                # Respond to heartbeats
                await self._handle_heartbeat(websocket, message)
                return
                
            # Dispatch to registered handler
            if content_type in self.message_handlers:
                try:
                    response_data = await self.message_handlers[content_type](message)
                    if response_data:
                        # Create a proper response envelope
                        response = {
                            "meta": {
                                "message_id": str(uuid.uuid4()),
                                "sender": self.authed.agent_id,
                                "recipient": sender_id,
                                "timestamp": self._get_iso_timestamp(),
                                "sequence": 0,
                                "channel_id": meta.get("channel_id", "unknown"),
                                "reply_to": meta.get("message_id", "")
                            },
                            "content": response_data
                        }
                        
                        # Record outgoing message if in test mode
                        if _TESTING:
                            record_outgoing(response, self.authed.agent_id, sender_id)
                        
                        # Check if this is a FastAPI WebSocket (has send_json method)
                        if hasattr(websocket, 'send_json'):
                            await websocket.send_json(response)
                        elif hasattr(websocket, 'send_text'):
                            await websocket.send_text(json.dumps(response))
                        else:
                            # Fallback to standard WebSocket
                            await websocket.send(json.dumps(response))
                except Exception as e:
                    logger.error(f"Error in message handler: {str(e)}", exc_info=True)
                    await self._send_error(
                        websocket, 
                        f"Error processing message: {str(e)}",
                        meta.get("message_id"),
                        sender_id
                    )
            else:
                # Make sure we have the required fields for the error message
                message_id = meta.get("message_id", None)
                
                await self._send_error(
                    websocket, 
                    f"Unsupported message type: {content_type}",
                    message_id,
                    sender_id
                )
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            try:
                meta = message.get("meta", {})
                sender_id = meta.get("sender_id", meta.get("sender", "anonymous"))
                message_id = meta.get("message_id", None)
                await self._send_error(websocket, f"Internal error: {str(e)}", message_id, sender_id)
            except Exception as inner_e:
                logger.error(f"Error sending error message: {str(inner_e)}", exc_info=True)
        
    async def _handle_channel_open(self, websocket, message):
        """Handle channel open request."""
        try:
            # Extract information
            meta = message.get("meta", {})
            channel_id = meta.get("channel_id", str(uuid.uuid4()))
            sender_id = meta.get("sender_id", meta.get("sender", "anonymous"))
            
            # Log the open event
            logger.info(f"Channel {channel_id} open requested by {sender_id}")
            
            # Create response
            response = {
                "meta": {
                    "message_id": str(uuid.uuid4()),
                    "sender": self.authed.agent_id,
                    "recipient": sender_id,
                    "timestamp": self._get_iso_timestamp(),
                    "sequence": 1,
                    "channel_id": channel_id,
                    "reply_to": meta.get("message_id", "")
                },
                "content": {
                    "type": MessageType.CHANNEL_ACCEPT,
                    "data": {
                        "protocol_version": "1.0",
                        "capabilities": ["json"]
                    }
                }
            }
            
            logger.debug(f"Sending channel accept response: {json.dumps(response, indent=2)}")
            
            # Record outgoing message if in test mode
            if _TESTING:
                record_outgoing(response, self.authed.agent_id, sender_id)
            
            # Check if this is a FastAPI WebSocket (has send_json method)
            if hasattr(websocket, 'send_json'):
                await websocket.send_json(response)
            elif hasattr(websocket, 'send_text'):
                await websocket.send_text(json.dumps(response))
            else:
                # Fallback to standard WebSocket
                await websocket.send(json.dumps(response))
                
            logger.debug(f"Sent channel accept for channel {channel_id}")
        except Exception as e:
            logger.error(f"Error in _handle_channel_open: {str(e)}", exc_info=True)
            raise
        
    async def _handle_channel_close(self, websocket, message):
        """Handle channel close request."""
        try:
            # Extract information
            meta = message.get("meta", {})
            channel_id = meta.get("channel_id", "unknown")
            sender_id = meta.get("sender_id", meta.get("sender", "anonymous"))
            reason = message.get("content", {}).get("data", {}).get("reason", "normal")
            
            # Log the close event
            logger.info(f"Channel {channel_id} close requested by {sender_id} with reason: {reason}")
            
            # Send acknowledgment
            response = {
                "meta": {
                    "message_id": str(uuid.uuid4()),
                    "sender": self.authed.agent_id,
                    "recipient": sender_id,
                    "timestamp": self._get_iso_timestamp(),
                    "sequence": 1,
                    "channel_id": channel_id,
                    "reply_to": meta.get("message_id", "")
                },
                "content": {
                    "type": MessageType.CHANNEL_CLOSE,
                    "data": {
                        "acknowledged": True,
                        "reason": reason
                    }
                }
            }
            
            # Record outgoing message if in test mode
            if _TESTING:
                record_outgoing(response, self.authed.agent_id, sender_id)
            
            try:
                # Check if this is a FastAPI WebSocket (has send_json method)
                if hasattr(websocket, 'send_json'):
                    await websocket.send_json(response)
                elif hasattr(websocket, 'send_text'):
                    await websocket.send_text(json.dumps(response))
                else:
                    # Fallback to standard WebSocket
                    await websocket.send(json.dumps(response))
                    
                logger.debug(f"Sent close acknowledgment for channel {channel_id}")
            except Exception as e:
                logger.warning(f"Failed to send close acknowledgment: {str(e)}")
            
            # Remove from active connections
            self.active_connections.pop(channel_id, None)
        except Exception as e:
            logger.error(f"Error in _handle_channel_close: {str(e)}", exc_info=True)
            raise
        
    async def _handle_heartbeat(self, websocket, message):
        """Handle heartbeat message."""
        try:
            # Extract information
            meta = message.get("meta", {})
            channel_id = meta.get("channel_id", "unknown")
            sender_id = meta.get("sender_id", meta.get("sender", "anonymous"))
            
            # Create response
            response = {
                "meta": {
                    "message_id": str(uuid.uuid4()),
                    "sender": self.authed.agent_id,
                    "recipient": sender_id,
                    "timestamp": self._get_iso_timestamp(),
                    "sequence": 0,
                    "channel_id": channel_id,
                    "reply_to": meta.get("message_id", "")
                },
                "content": {
                    "type": MessageType.HEARTBEAT,
                    "data": {}
                }
            }
            
            # Record outgoing message if in test mode
            if _TESTING:
                record_outgoing(response, self.authed.agent_id, sender_id)
            
            # Check if this is a FastAPI WebSocket (has send_json method)
            if hasattr(websocket, 'send_json'):
                await websocket.send_json(response)
            elif hasattr(websocket, 'send_text'):
                await websocket.send_text(json.dumps(response))
            else:
                # Fallback to standard WebSocket
                await websocket.send(json.dumps(response))
        except Exception as e:
            logger.error(f"Error in _handle_heartbeat: {str(e)}", exc_info=True)
            raise
        
    async def _send_error(self, websocket, error_message, reply_to=None, sender_id="anonymous"):
        """Send an error message to the client."""
        try:
            # Check if the WebSocket is still open before sending
            if hasattr(websocket, 'client_state'):
                from starlette.websockets import WebSocketState
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    logger.debug("WebSocket is already disconnected, not sending error message")
                    return
            
            error = {
                "meta": {
                    "message_id": str(uuid.uuid4()),
                    "sender": self.authed.agent_id,
                    "recipient": sender_id,
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
            
            # Record outgoing message if in test mode
            if _TESTING:
                record_outgoing(error, self.authed.agent_id, sender_id)
            
            # Check if this is a FastAPI WebSocket (has send_json method)
            if hasattr(websocket, 'send_json'):
                await websocket.send_json(error)
            elif hasattr(websocket, 'send_text'):
                await websocket.send_text(json.dumps(error))
            else:
                # Fallback to standard WebSocket
                await websocket.send(json.dumps(error))
        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}", exc_info=True)
        
    def _get_iso_timestamp(self):
        """Get current time as ISO 8601 string."""
        return datetime.now(timezone.utc).isoformat() 