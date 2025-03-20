"""
MCP-Authed Integration Adapter

This module provides adapters for integrating Authed authentication with Model Context Protocol (MCP) servers and clients.
"""

import json
import logging
from uuid import UUID
from typing import Any, Dict, Optional, Union, List


# Import Authed SDK
from authed import Authed

# Import MCP SDK
from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Tool, Prompt
from mcp import ClientSession
from mcp.client.sse import sse_client

# Configure logging
logger = logging.getLogger(__name__)

class AuthedMCPServer:
    """
    MCP server with Authed authentication.
    """
    
    def __init__(self, name: str, registry_url: str, agent_id: str, agent_secret: str, private_key: str, public_key: str):
        """
        Initialize the server with Authed credentials.
        
        Args:
            name: Name of the MCP server
            registry_url: URL of the Authed registry
            agent_id: ID of the agent
            agent_secret: Secret of the agent
            private_key: Private key of the agent
            public_key: Public key of the agent
        """
        self.name = name
        
        # Initialize Authed SDK
        logger.info(f"Initializing Authed SDK for server with agent_id: {agent_id}")
        self.authed = Authed.initialize(
            registry_url=registry_url,
            agent_id=agent_id,
            agent_secret=agent_secret,
            private_key=private_key,
            public_key=public_key
        )
        logger.info(f"Authed SDK initialized successfully for server")
        
        # Create MCP server
        self.mcp = FastMCP(name)

    def resource(self, path: str = None):
        """Register a resource handler."""
        return self.mcp.resource(path)
    
    def tool(self, name: str = None):
        """Register a tool handler."""
        return self.mcp.tool(name)
    
    def prompt(self, name: str = None):
        """Register a prompt handler."""
        return self.mcp.prompt(name)
    
    def run(self):
        """Run the MCP server."""
        # Let the MCP server handle its own event loop
        return self.mcp.run()


class AuthedMCPClient:
    """
    MCP client with Authed authentication using SSE transport.
    """
    
    def __init__(self, registry_url: str, agent_id: str, agent_secret: str, private_key: str, public_key: str = None):
        """Initialize the client with Authed credentials."""
        logger.info(f"Initializing Authed SDK for client with agent_id: {agent_id}")
        self.authed = Authed.initialize(
            registry_url=registry_url,
            agent_id=agent_id,
            agent_secret=agent_secret,
            private_key=private_key,
            public_key=public_key
        )
        logger.info(f"Authed SDK initialized successfully for client")
        self._sessions = {}  # Store active sessions
    
    async def create_session(self, server_url: str, server_agent_id: Union[str, UUID], method: str = "GET") -> ClientSession:
        """
        Create and maintain a persistent MCP session.
        
        This method keeps the SSE connection open and returns a session that will remain valid.
        """
        # Use the protect_request method to get properly formatted headers
        headers = await self.authed.auth.protect_request(
            method=method,
            url=server_url,
            target_agent_id=server_agent_id
        )
        
        logger.info(f"Creating persistent session to MCP server at {server_url}")
        
        # Create SSE client - NOT using a context manager
        from mcp.client.sse import sse_client
        
        # Generate a unique session ID to track this connection
        import uuid
        session_id = str(uuid.uuid4())
        
        # Store connection info for cleanup later
        self._sessions[session_id] = {
            "server_url": server_url,
            "server_agent_id": server_agent_id,
            "stream_manager": None,
            "session": None,
            "active": False
        }
        
        try:
            # Open connection without context manager so it stays open
            logger.info(f"Establishing direct SSE connection to {server_url}")
            stream_manager = sse_client(url=server_url, headers=headers)
            streams = await stream_manager.__aenter__()
            
            # Initialize session
            from mcp import ClientSession
            session = ClientSession(*streams)
            await session.initialize()
            
            # Store references for cleanup
            self._sessions[session_id]["stream_manager"] = stream_manager
            self._sessions[session_id]["session"] = session
            self._sessions[session_id]["active"] = True
            
            logger.info(f"Persistent MCP session created successfully with ID: {session_id}")
            return session
        except Exception as e:
            logger.error(f"Error creating persistent session: {str(e)}")
            # Clean up partial resources
            if session_id in self._sessions:
                await self.close_session(session_id)
            raise
    
    async def close_session(self, session_id: str):
        """Close a session and clean up resources."""
        if session_id not in self._sessions:
            logger.warning(f"Session {session_id} not found for cleanup")
            return
        
        session_info = self._sessions[session_id]
        logger.info(f"Closing session {session_id} to {session_info['server_url']}")
        
        # Close the session if it exists
        if session_info["session"]:
            try:
                await session_info["session"].close()
                logger.info(f"Session {session_id} closed")
            except Exception as e:
                logger.error(f"Error closing session {session_id}: {str(e)}")
        
        # Close the stream manager if it exists
        if session_info["stream_manager"]:
            try:
                await session_info["stream_manager"].__aexit__(None, None, None)
                logger.info(f"Stream for session {session_id} closed")
            except Exception as e:
                logger.error(f"Error closing stream for session {session_id}: {str(e)}")
        
        # Remove from active sessions
        self._sessions[session_id]["active"] = False
        del self._sessions[session_id]
    
    async def close_all_sessions(self):
        """Close all active sessions."""
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)
    
    async def connect_and_execute(self, server_url: str, server_agent_id: Union[str, UUID], operation, method: str = "GET"):
        """
        Connect to an MCP server and execute an operation.
        
        NOTE: If you're trying to get a persistent session, use create_session instead.
        This method is for one-off operations only.
        """
        # Create a session
        session = await self.create_session(server_url, server_agent_id, method)
        
        # Generate session ID for tracking
        session_id = next(key for key, value in self._sessions.items() 
                         if value["session"] == session)
        
        try:
            # Execute the operation
            logger.info(f"Executing MCP operation on session {session_id}")
            result = await operation(session)
            logger.info(f"MCP operation completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error during MCP operation: {str(e)}")
            raise
        finally:
            # Only close the session if operation was lambda session: session
            # Otherwise keep it open for persistent use
            import inspect
            operation_src = inspect.getsource(operation).strip()
            if "lambda" in operation_src and "session: session" in operation_src:
                logger.info("Not closing session as it's being returned for persistent use")
            else:
                await self.close_session(session_id)
    
    async def list_resources(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Resource]:
        """List resources from an MCP server."""
        logger.info(f"Listing resources from server: {server_agent_id}")
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.list_resources()
        )
    
    async def list_tools(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Tool]:
        """List tools from an MCP server."""
        logger.info(f"Listing tools from server: {server_agent_id}")
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.list_tools()
        )
    
    async def list_prompts(self, server_url: str, server_agent_id: Union[str, UUID]) -> List[Prompt]:
        """List prompts from an MCP server."""
        logger.info(f"Listing prompts from server: {server_agent_id}")
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.list_prompts()
        )
    
    async def read_resource(self, server_url: str, server_agent_id: Union[str, UUID], resource_id: str) -> tuple:
        """Read a resource from an MCP server."""
        logger.info(f"Reading resource {resource_id} from server: {server_agent_id}")
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.read_resource(resource_id)
        )
    
    async def call_tool(self, server_url: str, server_agent_id: Union[str, UUID], tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """Call a tool on an MCP server."""
        logger.info(f"Calling tool {tool_name} on server: {server_agent_id} with arguments: {arguments}")
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.call_tool(tool_name, arguments or {})
        )
    
    async def get_prompt(self, server_url: str, server_agent_id: Union[str, UUID], prompt_name: str, arguments: Dict[str, str] = None) -> Any:
        """Get a prompt from an MCP server."""
        logger.info(f"Getting prompt {prompt_name} from server: {server_agent_id} with arguments: {arguments}")
        return await self.connect_and_execute(
            server_url, 
            server_agent_id,
            lambda session: session.get_prompt(prompt_name, arguments or {})
        )