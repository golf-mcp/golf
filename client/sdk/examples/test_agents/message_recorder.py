"""Message recorder for WebSocket communication testing.

This module provides utilities to record and analyze WebSocket messages
during testing. It's designed to be non-intrusive and only used in test environments.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class MessageRecorder:
    """Records WebSocket messages for testing and debugging purposes."""
    
    def __init__(self, output_dir: str = None, enabled: bool = True):
        """Initialize the message recorder.
        
        Args:
            output_dir: Directory to save message logs (defaults to current directory)
            enabled: Whether recording is enabled
        """
        self.enabled = enabled
        self.output_dir = output_dir or os.getcwd()
        self.messages: List[Dict[str, Any]] = []
        self.exchanges: List[Dict[str, Any]] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create a unique session file
        self.log_file = os.path.join(self.output_dir, f"ws_session_{self.session_id}.json")
        
        logger.info(f"Message recorder initialized. Recording to {self.log_file}")
    
    def record_message(self, 
                      direction: str, 
                      message: Dict[str, Any], 
                      source_id: str, 
                      target_id: str):
        """Record a WebSocket message.
        
        Args:
            direction: "SEND" or "RECEIVE"
            message: The message content
            source_id: ID of the sending agent
            target_id: ID of the receiving agent
        """
        if not self.enabled:
            return
            
        timestamp = datetime.now().isoformat()
        
        record = {
            "timestamp": timestamp,
            "direction": direction,
            "source_id": source_id,
            "target_id": target_id,
            "message": message
        }
        
        self.messages.append(record)
        
        # Try to match request/response pairs
        if direction == "RECEIVE" and "meta" in message and "reply_to" in message["meta"] and message["meta"]["reply_to"]:
            reply_to = message["meta"]["reply_to"]
            # Find the original message
            for idx, msg in enumerate(self.messages):
                if (msg["direction"] == "SEND" and 
                    "message" in msg and 
                    "meta" in msg["message"] and 
                    "message_id" in msg["message"]["meta"] and
                    msg["message"]["meta"]["message_id"] == reply_to):
                    
                    exchange = {
                        "request": msg,
                        "response": record,
                        "round_trip_ms": (datetime.fromisoformat(timestamp) - 
                                         datetime.fromisoformat(msg["timestamp"])).total_seconds() * 1000
                    }
                    self.exchanges.append(exchange)
                    break
        
        # Save after each message to ensure we don't lose data
        self._save_to_file()
    
    def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a message by its ID.
        
        Args:
            message_id: The message ID to find
            
        Returns:
            The message record or None if not found
        """
        for msg in self.messages:
            if ("message" in msg and 
                "meta" in msg["message"] and 
                "message_id" in msg["message"]["meta"] and
                msg["message"]["meta"]["message_id"] == message_id):
                return msg
        return None
    
    def get_exchanges_by_type(self, content_type: str) -> List[Dict[str, Any]]:
        """Get all request/response exchanges of a specific type.
        
        Args:
            content_type: The content type to filter by
            
        Returns:
            List of matching exchanges
        """
        result = []
        for exchange in self.exchanges:
            if ("request" in exchange and 
                "message" in exchange["request"] and 
                "content" in exchange["request"]["message"] and
                "type" in exchange["request"]["message"]["content"] and
                exchange["request"]["message"]["content"]["type"] == content_type):
                result.append(exchange)
        return result
    
    def get_messages_by_channel(self, channel_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a specific channel.
        
        Args:
            channel_id: The channel ID to filter by
            
        Returns:
            List of messages in the channel
        """
        result = []
        for msg in self.messages:
            if ("message" in msg and 
                "meta" in msg["message"] and 
                "channel_id" in msg["message"]["meta"] and
                msg["message"]["meta"]["channel_id"] == channel_id):
                result.append(msg)
        return result
    
    def print_summary(self):
        """Print a summary of recorded messages."""
        if not self.enabled or not self.messages:
            logger.info("No messages recorded")
            return
            
        total_messages = len(self.messages)
        sent = sum(1 for m in self.messages if m["direction"] == "SEND")
        received = sum(1 for m in self.messages if m["direction"] == "RECEIVE")
        
        channels = set()
        message_types = {}
        
        for msg in self.messages:
            if "message" in msg and "meta" in msg["message"] and "channel_id" in msg["message"]["meta"]:
                channels.add(msg["message"]["meta"]["channel_id"])
                
            if "message" in msg and "content" in msg["message"] and "type" in msg["message"]["content"]:
                msg_type = msg["message"]["content"]["type"]
                message_types[msg_type] = message_types.get(msg_type, 0) + 1
        
        logger.info(f"Message Recording Summary:")
        logger.info(f"  Total messages: {total_messages}")
        logger.info(f"  Sent: {sent}, Received: {received}")
        logger.info(f"  Channels: {len(channels)}")
        logger.info(f"  Message types: {message_types}")
        logger.info(f"  Exchanges: {len(self.exchanges)}")
        logger.info(f"  Log file: {self.log_file}")
    
    def _save_to_file(self):
        """Save recorded messages to a JSON file."""
        if not self.enabled:
            return
            
        data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "messages": self.messages,
            "exchanges": self.exchanges
        }
        
        try:
            with open(self.log_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save message log: {str(e)}")

# Global recorder instance
recorder = MessageRecorder(enabled=os.environ.get("RECORD_WS_MESSAGES", "0") == "1")

def record_outgoing(message: Dict[str, Any], source_id: str, target_id: str):
    """Record an outgoing message."""
    recorder.record_message("SEND", message, source_id, target_id)

def record_incoming(message: Dict[str, Any], source_id: str, target_id: str):
    """Record an incoming message."""
    recorder.record_message("RECEIVE", message, source_id, target_id)

def get_recorder() -> MessageRecorder:
    """Get the global recorder instance."""
    return recorder 