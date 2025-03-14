#!/usr/bin/env python3
"""Script to run both test agents and test the WebSocket channel handshake."""

import asyncio
import json
import logging
import os
import subprocess
import sys
import httpx
import argparse
from pathlib import Path
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
AGENT_A_PORT = 8000
AGENT_B_PORT = 8001

# Default registry URL (production)
DEFAULT_REGISTRY_URL = "https://api.getauthed.dev"

# Enable message recording for testing
os.environ["AUTHED_TESTING"] = "1"
os.environ["RECORD_WS_MESSAGES"] = "1"

async def wait_for_agent(url: str, max_retries: int = 10, retry_delay: float = 1.0) -> bool:
    """Wait for an agent to be ready."""
    for i in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/health", timeout=5.0)
                if response.status_code == 200:
                    logger.info(f"Agent at {url} is ready")
                    return True
        except Exception as e:
            logger.debug(f"Agent at {url} not ready yet: {str(e)}")
        
        logger.info(f"Waiting for agent at {url} to be ready (attempt {i+1}/{max_retries})...")
        await asyncio.sleep(retry_delay)
    
    logger.error(f"Agent at {url} failed to start after {max_retries} attempts")
    return False

async def display_message_logs():
    """Display recorded message logs if available."""
    try:
        # Find the most recent message log file
        log_files = glob.glob("ws_session_*.json")
        if not log_files:
            logger.warning("No message log files found")
            return
            
        # Sort by modification time (most recent first)
        latest_log = max(log_files, key=os.path.getmtime)
        logger.info(f"Loading message log from: {latest_log}")
        
        # Load the log file
        with open(latest_log, 'r') as f:
            log_data = json.load(f)
            
        messages = log_data.get("messages", [])
        exchanges = log_data.get("exchanges", [])
        
        if not messages:
            logger.warning("No messages found in log file")
            return
            
        # Print summary
        total_messages = len(messages)
        sent = sum(1 for m in messages if m["direction"] == "SEND")
        received = sum(1 for m in messages if m["direction"] == "RECEIVE")
        
        channels = set()
        message_types = {}
        
        for msg in messages:
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
        logger.info(f"  Exchanges: {len(exchanges)}")
        
        # Get all channel open/accept exchanges
        channel_opens = [ex for ex in exchanges if 
                        "request" in ex and 
                        "message" in ex["request"] and 
                        "content" in ex["request"]["message"] and
                        "type" in ex["request"]["message"]["content"] and
                        ex["request"]["message"]["content"]["type"] == "channel.open"]
        
        if channel_opens:
            logger.info(f"\nFound {len(channel_opens)} channel open/accept exchanges")
            for i, exchange in enumerate(channel_opens):
                logger.info(f"\n=== Channel Exchange {i+1} ===")
                req = exchange["request"]["message"]
                resp = exchange["response"]["message"]
                
                # Request details
                logger.info(f"REQUEST:")
                logger.info(f"  Type: {req['content']['type']}")
                logger.info(f"  From: {req['meta']['sender']} To: {req['meta']['recipient']}")
                logger.info(f"  Channel: {req['meta']['channel_id']}")
                logger.info(f"  Message ID: {req['meta']['message_id']}")
                logger.info(f"  Timestamp: {req['meta']['timestamp']}")
                logger.info(f"  Data: {json.dumps(req['content']['data'], indent=2)}")
                
                # Response details
                logger.info(f"RESPONSE:")
                logger.info(f"  Type: {resp['content']['type']}")
                logger.info(f"  From: {resp['meta']['sender']} To: {resp['meta']['recipient']}")
                logger.info(f"  Channel: {resp['meta']['channel_id']}")
                logger.info(f"  Message ID: {resp['meta']['message_id']}")
                logger.info(f"  Reply To: {resp['meta']['reply_to']}")
                logger.info(f"  Timestamp: {resp['meta']['timestamp']}")
                logger.info(f"  Data: {json.dumps(resp['content']['data'], indent=2)}")
                
                logger.info(f"  Round trip: {exchange['round_trip_ms']:.2f}ms")
                
        # Get all application message exchanges
        app_messages = [ex for ex in exchanges if 
                       "request" in ex and 
                       "message" in ex["request"] and 
                       "content" in ex["request"]["message"] and
                       "type" in ex["request"]["message"]["content"] and
                       ex["request"]["message"]["content"]["type"] not in 
                       ["channel.open", "channel.close", "channel.accept", "heartbeat"]]
        
        if app_messages:
            logger.info(f"\nFound {len(app_messages)} application message exchanges")
            for i, exchange in enumerate(app_messages):
                logger.info(f"\n=== App Message Exchange {i+1} ===")
                req = exchange["request"]["message"]
                resp = exchange["response"]["message"]
                
                # Request details
                logger.info(f"REQUEST:")
                logger.info(f"  Type: {req['content']['type']}")
                logger.info(f"  From: {req['meta']['sender']} To: {req['meta']['recipient']}")
                logger.info(f"  Channel: {req['meta']['channel_id']}")
                logger.info(f"  Message ID: {req['meta']['message_id']}")
                logger.info(f"  Timestamp: {req['meta']['timestamp']}")
                logger.info(f"  Data: {json.dumps(req['content']['data'], indent=2)}")
                
                # Response details
                logger.info(f"RESPONSE:")
                logger.info(f"  Type: {resp['content']['type']}")
                logger.info(f"  From: {resp['meta']['sender']} To: {resp['meta']['recipient']}")
                logger.info(f"  Channel: {resp['meta']['channel_id']}")
                logger.info(f"  Message ID: {resp['meta']['message_id']}")
                logger.info(f"  Reply To: {resp['meta']['reply_to']}")
                logger.info(f"  Timestamp: {resp['meta']['timestamp']}")
                logger.info(f"  Data: {json.dumps(resp['content']['data'], indent=2)}")
                
                logger.info(f"  Round trip: {exchange['round_trip_ms']:.2f}ms")
                
        # Show file location
        logger.info(f"\nMessage log file: {latest_log}")
                
    except ImportError:
        logger.warning("Message recorder not available")
    except Exception as e:
        logger.error(f"Error displaying message logs: {str(e)}")

async def test_websocket_handshake(
    agent_a_id: str,
    agent_a_secret: str,
    agent_b_id: str,
    agent_b_secret: str,
    registry_url: str,
    agent_a_private_key: str = None,
    agent_a_public_key: str = None,
    agent_b_private_key: str = None,
    agent_b_public_key: str = None,
    verbose: bool = False
) -> bool:
    """Test the WebSocket channel handshake between agents."""
    # WebSocket URLs
    agent_a_ws_url = f"ws://localhost:{AGENT_A_PORT}/ws"
    agent_b_ws_url = f"ws://localhost:{AGENT_B_PORT}/ws"
    
    try:
        # Start both agents
        logger.info("Starting Agent A...")
        agent_a_env = os.environ.copy()
        agent_a_env.update({
            "AGENT_A_ID": agent_a_id,
            "AGENT_A_SECRET": agent_a_secret,
            "AGENT_B_ID": agent_b_id,
            "AGENT_B_WS_URL": agent_b_ws_url,
            "REGISTRY_URL": registry_url,
            "PORT": str(AGENT_A_PORT),
            "AUTHED_TESTING": "1",
            "RECORD_WS_MESSAGES": "1"
        })
        
        # Add keys if provided
        if agent_a_private_key:
            agent_a_env["AGENT_A_PRIVATE_KEY"] = agent_a_private_key
        if agent_a_public_key:
            agent_a_env["AGENT_A_PUBLIC_KEY"] = agent_a_public_key
            
        agent_a_process = subprocess.Popen(
            [sys.executable, "agent_a.py"],
            env=agent_a_env,
            cwd=Path(__file__).parent
        )
        
        logger.info("Starting Agent B...")
        agent_b_env = os.environ.copy()
        agent_b_env.update({
            "AGENT_B_ID": agent_b_id,
            "AGENT_B_SECRET": agent_b_secret,
            "AGENT_A_ID": agent_a_id,
            "AGENT_A_WS_URL": agent_a_ws_url,
            "REGISTRY_URL": registry_url,
            "PORT": str(AGENT_B_PORT),
            "AUTHED_TESTING": "1",
            "RECORD_WS_MESSAGES": "1"
        })
        
        # Add keys if provided
        if agent_b_private_key:
            agent_b_env["AGENT_B_PRIVATE_KEY"] = agent_b_private_key
        if agent_b_public_key:
            agent_b_env["AGENT_B_PUBLIC_KEY"] = agent_b_public_key
            
        agent_b_process = subprocess.Popen(
            [sys.executable, "agent_b.py"],
            env=agent_b_env,
            cwd=Path(__file__).parent
        )
        
        # Wait for both agents to be ready
        agent_a_ready = await wait_for_agent(f"http://localhost:{AGENT_A_PORT}")
        agent_b_ready = await wait_for_agent(f"http://localhost:{AGENT_B_PORT}")
        
        if not (agent_a_ready and agent_b_ready):
            logger.error("Failed to start one or both agents")
            return False
        
        # Test Agent A connecting to Agent B
        logger.info("Testing Agent A connecting to Agent B...")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:{AGENT_A_PORT}/connect-to-agent-b")
            logger.info(f"Agent A to Agent B test result: {response.status_code}")
            logger.info(f"Response: {response.json()}")
            
            if response.status_code != 200 or response.json().get("status") != "success":
                logger.error("Agent A to Agent B test failed")
                return False
                
        # Test Agent B connecting to Agent A
        logger.info("Testing Agent B connecting to Agent A...")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:{AGENT_B_PORT}/connect-to-agent-a")
            logger.info(f"Agent B to Agent A test result: {response.status_code}")
            logger.info(f"Response: {response.json()}")
            
            if response.status_code != 200 or response.json().get("status") != "success":
                logger.error("Agent B to Agent A test failed")
                return False
        
        # Display message logs if verbose
        if verbose:
            await display_message_logs()
        
        logger.info("All tests passed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        return False
    finally:
        # Terminate the agent processes
        logger.info("Terminating agent processes...")
        try:
            agent_a_process.terminate()
            agent_b_process.terminate()
            
            # Wait for processes to terminate
            agent_a_process.wait(timeout=5)
            agent_b_process.wait(timeout=5)
        except Exception as e:
            logger.error(f"Error terminating agent processes: {str(e)}")
            # Force kill if terminate fails
            try:
                agent_a_process.kill()
                agent_b_process.kill()
            except:
                pass

def load_credentials(file_path: str) -> dict:
    """Load agent credentials from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            creds = json.load(f)
            
            # Transform the credentials into the expected format
            return {
                "agent_a_id": creds.get("agent_a_id"),
                "agent_a_secret": creds.get("agent_a_secret"),
                "agent_b_id": creds.get("agent_b_id"),
                "agent_b_secret": creds.get("agent_b_secret"),
                "agent_a_private_key": creds.get("agent_a_private_key"),
                "agent_a_public_key": creds.get("agent_a_public_key"),
                "agent_b_private_key": creds.get("agent_b_private_key"),
                "agent_b_public_key": creds.get("agent_b_public_key")
            }
    except Exception as e:
        logger.error(f"Error loading credentials from {file_path}: {str(e)}")
        sys.exit(1)

async def main():
    """Run the test."""
    parser = argparse.ArgumentParser(description="Test WebSocket channel handshake between agents")
    
    # Agent credentials
    parser.add_argument("--agent-a-id", help="Agent A ID")
    parser.add_argument("--agent-a-secret", help="Agent A secret")
    parser.add_argument("--agent-b-id", help="Agent B ID")
    parser.add_argument("--agent-b-secret", help="Agent B secret")
    
    # Agent keys
    parser.add_argument("--agent-a-private-key", help="Agent A private key")
    parser.add_argument("--agent-a-public-key", help="Agent A public key")
    parser.add_argument("--agent-b-private-key", help="Agent B private key")
    parser.add_argument("--agent-b-public-key", help="Agent B public key")
    
    # Credential files
    parser.add_argument("--creds-file", help="JSON file containing agent credentials")
    
    # Registry URL
    parser.add_argument("--registry-url", default=DEFAULT_REGISTRY_URL, help="Registry URL")
    
    # Verbose output
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output with message logs")
    
    args = parser.parse_args()
    
    # Load credentials from file if provided
    if args.creds_file:
        creds = load_credentials(args.creds_file)
        agent_a_id = creds.get("agent_a_id")
        agent_a_secret = creds.get("agent_a_secret")
        agent_b_id = creds.get("agent_b_id")
        agent_b_secret = creds.get("agent_b_secret")
        agent_a_private_key = creds.get("agent_a_private_key")
        agent_a_public_key = creds.get("agent_a_public_key")
        agent_b_private_key = creds.get("agent_b_private_key")
        agent_b_public_key = creds.get("agent_b_public_key")
    else:
        # Use command line arguments or environment variables
        agent_a_id = args.agent_a_id or os.environ.get("AGENT_A_ID")
        agent_a_secret = args.agent_a_secret or os.environ.get("AGENT_A_SECRET")
        agent_b_id = args.agent_b_id or os.environ.get("AGENT_B_ID")
        agent_b_secret = args.agent_b_secret or os.environ.get("AGENT_B_SECRET")
        agent_a_private_key = args.agent_a_private_key or os.environ.get("AGENT_A_PRIVATE_KEY")
        agent_a_public_key = args.agent_a_public_key or os.environ.get("AGENT_A_PUBLIC_KEY")
        agent_b_private_key = args.agent_b_private_key or os.environ.get("AGENT_B_PRIVATE_KEY")
        agent_b_public_key = args.agent_b_public_key or os.environ.get("AGENT_B_PUBLIC_KEY")
    
    # Check if we have all required credentials
    if not all([agent_a_id, agent_a_secret, agent_b_id, agent_b_secret]):
        logger.error("Missing agent credentials. Please provide them via command line arguments, environment variables, or a credentials file.")
        parser.print_help()
        sys.exit(1)
    
    # Get registry URL
    registry_url = args.registry_url or os.environ.get("REGISTRY_URL", DEFAULT_REGISTRY_URL)
    
    logger.info(f"Using registry URL: {registry_url}")
    logger.info(f"Agent A ID: {agent_a_id}")
    logger.info(f"Agent B ID: {agent_b_id}")
    
    # Run the test
    success = await test_websocket_handshake(
        agent_a_id=agent_a_id,
        agent_a_secret=agent_a_secret,
        agent_b_id=agent_b_id,
        agent_b_secret=agent_b_secret,
        registry_url=registry_url,
        agent_a_private_key=agent_a_private_key,
        agent_a_public_key=agent_a_public_key,
        agent_b_private_key=agent_b_private_key,
        agent_b_public_key=agent_b_public_key,
        verbose=args.verbose
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main()) 