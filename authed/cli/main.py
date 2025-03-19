"""Command line interface for Agent Auth."""

import click
import json
from pathlib import Path
from uuid import UUID
from .commands import agents, permissions, keys, logs, init
from .auth import CLIAuth

# Config file location
CONFIG_DIR = Path.home() / '.authed'
CONFIG_FILE = CONFIG_DIR / 'config.json'

def load_config():
    """Load configuration from file."""
    if not CONFIG_FILE.exists():
        return {}
    
    with CONFIG_FILE.open('r') as f:
        return json.load(f)

@click.group()
@click.option(
    '--debug',
    is_flag=True,
    help='Enable debug mode'
)
@click.option(
    '--registry-url',
    envvar='AUTHED_REGISTRY_URL',
    help='URL of the Agent Auth registry service'
)
@click.option(
    '--provider-id',
    envvar='AUTHED_PROVIDER_ID',
    help='Provider ID for authentication'
)
@click.option(
    '--provider-secret',
    envvar='AUTHED_PROVIDER_SECRET',
    help='Provider secret for authentication'
)
@click.pass_context
def cli(ctx, debug: bool, registry_url: str, provider_id: str, provider_secret: str):
    """Authed CLI - Manage agents and permissions for a provider.
    
    Configuration can be provided in three ways (in order of precedence):
    1. Command line arguments
    2. Environment variables
    3. Configuration file (~/.authed/config.json)
    
    Run 'authed init config' to set up configuration interactively.
    """
    # Load config from file
    config = load_config()
    
    # Use values in order: args > env > config
    registry_url = registry_url or config.get('registry_url')
    provider_id = provider_id or config.get('provider_id')
    provider_secret = provider_secret or config.get('provider_secret')
    
    # Skip auth initialization for init commands
    if ctx.invoked_subcommand == 'init':
        return
    
    # Ensure we have all required values
    if not all([registry_url, provider_id, provider_secret]):
        raise click.UsageError(
            "Missing required credentials. Either:\n"
            "1. Provide them as arguments\n"
            "2. Set them as environment variables\n"
            "3. Run 'agent-auth init config' to configure"
        )
    
    # Initialize auth
    try:
        auth = CLIAuth(
            registry_url=registry_url,
            provider_id=UUID(provider_id),
            provider_secret=provider_secret,
            debug=debug  # Pass debug flag to CLIAuth
        )
    except ValueError as e:
        raise click.UsageError(str(e))
    
    # Store in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['auth'] = auth
    ctx.obj['provider_id'] = provider_id
    ctx.obj['debug'] = debug  # Store debug flag in context

# Add command groups
cli.add_command(agents.group)
cli.add_command(permissions.group)
cli.add_command(keys.group)
cli.add_command(logs.group)
cli.add_command(init.group)

if __name__ == '__main__':
    cli() 