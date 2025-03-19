"""
Authed MCP Client CLI

A command-line tool for interacting with MCP servers using Authed authentication.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Optional

from .adapter import AuthedMCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def configure_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(log_level)
    if verbose:
        logging.getLogger('authed.sdk').setLevel(logging.DEBUG)
        logging.getLogger('authed.sdk.auth').setLevel(logging.DEBUG)
    else:
        logging.getLogger('authed.sdk').setLevel(logging.INFO)
        logging.getLogger('authed.sdk.auth').setLevel(logging.INFO)


async def create_client(registry_url: Optional[str] = None,
                       agent_id: Optional[str] = None,
                       agent_secret: Optional[str] = None,
                       private_key: Optional[str] = None,
                       public_key: Optional[str] = None) -> AuthedMCPClient:
    """
    Create an MCP client with Authed authentication.
    
    Args:
        registry_url: URL of the Authed registry
        agent_id: ID of the agent
        agent_secret: Secret of the agent
        private_key: Private key of the agent
        public_key: Public key of the agent
        
    Returns:
        AuthedMCPClient: Initialized client
    """
    # Use parameters if provided, otherwise fall back to environment variables
    registry_url = registry_url or os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev")
    agent_id = agent_id or os.getenv("AUTHED_AGENT_ID")
    agent_secret = agent_secret or os.getenv("AUTHED_AGENT_SECRET")
    private_key = private_key or os.getenv("AUTHED_PRIVATE_KEY")
    public_key = public_key or os.getenv("AUTHED_PUBLIC_KEY")
    
    # Validate required parameters
    if not all([agent_id, agent_secret, private_key]):
        raise ValueError(
            "Missing required credentials. Provide them as parameters or "
            "set AUTHED_AGENT_ID, AUTHED_AGENT_SECRET, and AUTHED_PRIVATE_KEY "
            "environment variables."
        )
    
    # Create MCP client with Authed authentication
    logger.debug("Creating AuthedMCPClient...")
    client = AuthedMCPClient(
        registry_url=registry_url,
        agent_id=agent_id,
        agent_secret=agent_secret,
        private_key=private_key,
        public_key=public_key
    )
    logger.debug("AuthedMCPClient created successfully")
    
    return client


async def list_resources(args: argparse.Namespace) -> None:
    """List resources from an MCP server."""
    client = await create_client()
    
    try:
        resources = await client.list_resources(args.server_url, args.server_agent_id)
        print(json.dumps([r.to_dict() for r in resources], indent=2))
    except Exception as e:
        logger.error(f"Error listing resources: {str(e)}")
        if args.verbose:
            logger.exception(e)
        sys.exit(1)


async def list_tools(args: argparse.Namespace) -> None:
    """List tools from an MCP server."""
    client = await create_client()
    
    try:
        tools = await client.list_tools(args.server_url, args.server_agent_id)
        print(json.dumps([t.to_dict() for t in tools], indent=2))
    except Exception as e:
        logger.error(f"Error listing tools: {str(e)}")
        if args.verbose:
            logger.exception(e)
        sys.exit(1)


async def list_prompts(args: argparse.Namespace) -> None:
    """List prompts from an MCP server."""
    client = await create_client()
    
    try:
        prompts = await client.list_prompts(args.server_url, args.server_agent_id)
        print(json.dumps([p.to_dict() for p in prompts], indent=2))
    except Exception as e:
        logger.error(f"Error listing prompts: {str(e)}")
        if args.verbose:
            logger.exception(e)
        sys.exit(1)


async def call_tool(args: argparse.Namespace) -> None:
    """Call a tool on an MCP server."""
    client = await create_client()
    
    # Parse tool arguments
    try:
        arguments = json.loads(args.arguments) if args.arguments else {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing tool arguments: {str(e)}")
        sys.exit(1)
    
    try:
        result = await client.call_tool(
            server_url=args.server_url,
            server_agent_id=args.server_agent_id,
            tool_name=args.tool_name,
            arguments=arguments
        )
        print(json.dumps(result, indent=2))
    except Exception as e:
        logger.error(f"Error calling tool: {str(e)}")
        if args.verbose:
            logger.exception(e)
        sys.exit(1)


async def get_prompt(args: argparse.Namespace) -> None:
    """Get a prompt from an MCP server."""
    client = await create_client()
    
    # Parse prompt arguments
    try:
        arguments = json.loads(args.arguments) if args.arguments else {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing prompt arguments: {str(e)}")
        sys.exit(1)
    
    try:
        result = await client.get_prompt(
            server_url=args.server_url,
            server_agent_id=args.server_agent_id,
            prompt_name=args.prompt_name,
            arguments=arguments
        )
        print(result)
    except Exception as e:
        logger.error(f"Error getting prompt: {str(e)}")
        if args.verbose:
            logger.exception(e)
        sys.exit(1)


async def read_resource(args: argparse.Namespace) -> None:
    """Read a resource from an MCP server."""
    client = await create_client()
    
    try:
        content, mime_type = await client.read_resource(
            server_url=args.server_url,
            server_agent_id=args.server_agent_id,
            resource_id=args.resource_id
        )
        print(f"MIME Type: {mime_type}")
        print("\nContent:")
        print(content)
    except Exception as e:
        logger.error(f"Error reading resource: {str(e)}")
        if args.verbose:
            logger.exception(e)
        sys.exit(1)


def main() -> None:
    """Run the MCP client CLI."""
    parser = argparse.ArgumentParser(description="Authed MCP Client CLI")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    # Common arguments
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--server-url", required=True, help="MCP server URL")
    common_parser.add_argument("--server-agent-id", required=True, help="MCP server agent ID")
    
    # Subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List resources command
    list_resources_parser = subparsers.add_parser(
        "list-resources", 
        parents=[common_parser],
        help="List resources from an MCP server"
    )
    list_resources_parser.set_defaults(func=list_resources)
    
    # List tools command
    list_tools_parser = subparsers.add_parser(
        "list-tools", 
        parents=[common_parser],
        help="List tools from an MCP server"
    )
    list_tools_parser.set_defaults(func=list_tools)
    
    # List prompts command
    list_prompts_parser = subparsers.add_parser(
        "list-prompts", 
        parents=[common_parser],
        help="List prompts from an MCP server"
    )
    list_prompts_parser.set_defaults(func=list_prompts)
    
    # Call tool command
    call_tool_parser = subparsers.add_parser(
        "call-tool", 
        parents=[common_parser],
        help="Call a tool on an MCP server"
    )
    call_tool_parser.add_argument("--tool-name", "-t", required=True, help="Name of the tool to call")
    call_tool_parser.add_argument("--arguments", "-a", help="JSON string of arguments for the tool")
    call_tool_parser.set_defaults(func=call_tool)
    
    # Get prompt command
    get_prompt_parser = subparsers.add_parser(
        "get-prompt", 
        parents=[common_parser],
        help="Get a prompt from an MCP server"
    )
    get_prompt_parser.add_argument("--prompt-name", "-p", required=True, help="Name of the prompt to get")
    get_prompt_parser.add_argument("--arguments", "-a", help="JSON string of arguments for the prompt")
    get_prompt_parser.set_defaults(func=get_prompt)
    
    # Read resource command
    read_resource_parser = subparsers.add_parser(
        "read-resource", 
        parents=[common_parser],
        help="Read a resource from an MCP server"
    )
    read_resource_parser.add_argument("--resource-id", "-r", required=True, help="ID of the resource to read")
    read_resource_parser.set_defaults(func=read_resource)
    
    args = parser.parse_args()
    
    # Configure logging
    configure_logging(args.verbose)
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    # Run the command
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main() 