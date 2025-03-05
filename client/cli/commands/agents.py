"""Agent management commands."""

import click
from typing import Optional
import json
from pathlib import Path
from ..utils import async_command

@click.group(name='agents')
def group():
    """Manage agents."""
    pass

@group.command(name='list')
@click.option('--output', type=click.Path(dir_okay=False), help='Save output to JSON file')
@click.pass_context
def list_agents(ctx, output: Optional[str]):
    """List all agents."""
    try:
        # Get auth from context
        auth = ctx.obj['auth']
        
        # Make authenticated request to registry
        response = auth.list_agents()
        
        if response.status_code == 401:
            raise click.UsageError("Authentication failed")
        elif response.status_code != 200:
            raise click.UsageError(f"Error: {response.text}")
            
        agents = response.json()['agents']
        
        # Format output
        formatted_agents = [
            {
                "agent_id": agent['agent_id'],
                "name": agent['name'],
                "provider_id": agent['provider_id'],
                "created_at": agent['created_at'],
                "updated_at": agent.get('updated_at'),
                "permissions": [
                    {
                        "type": perm['type'],
                        "target_id": perm['target_id']
                    }
                    for perm in agent.get('permissions', [])
                ]
            }
            for agent in agents
        ]
        
        if output:
            # Save to file
            output_path = Path(output)
            with output_path.open('w') as f:
                json.dump(formatted_agents, f, indent=2)
            click.echo(click.style("✓", fg="green", bold=True) + f" Agents list saved to {click.style(output, fg='blue')}")
        else:
            # Print to console
            click.echo("\n" + "=" * 60)
            click.echo(click.style("Registered Agents", fg="blue", bold=True))
            click.echo("=" * 60)
            
            if formatted_agents:
                for agent in formatted_agents:
                    click.echo(f"\n{click.style('●', fg='cyan')} {click.style(agent['name'], bold=True)} ({click.style(agent['agent_id'], fg='yellow')})")
                    click.echo(f"  Provider: {click.style(agent['provider_id'], fg='magenta')}")
                    click.echo(f"  Created:  {click.style(agent['created_at'], fg='bright_black')}")
                    if agent['updated_at']:
                        click.echo(f"  Updated:  {click.style(agent['updated_at'], fg='bright_black')}")
                    
                    if agent['permissions']:
                        click.echo("  Permissions:")
                        for perm in agent['permissions']:
                            perm_type = click.style("AGENT", fg="cyan") if perm['type'] == 'allow_agent' else click.style("PROVIDER", fg="magenta")
                            click.echo(f"    • {perm_type} → {click.style(perm['target_id'], fg='yellow')}")
                    click.echo(click.style("  " + "-" * 40, fg="bright_black"))
            else:
                click.echo("\n" + click.style("No agents found", fg="yellow", italic=True))
                
            click.echo()
                
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1)

@group.command(name='create')
@click.option('--provider-id', help='Provider ID to register agent under (overrides configured value)')
@click.option('--name', help='Agent name')
@click.option('--key-file', type=click.Path(exists=True), help='Path to key file (if not provided, will generate new keys)')
@click.pass_context
@async_command
async def create_agent(ctx, provider_id: Optional[str], name: Optional[str], key_file: Optional[str]):
    """Create a new agent."""
    try:
        # Get provider ID from args or context
        effective_provider_id = provider_id or ctx.obj.get('provider_id')
        if not effective_provider_id:
            raise click.UsageError(
                "No provider ID specified. Either:\n"
                "1. Provide --provider-id option\n"
                "2. Configure it with 'authed init config'\n"
                "3. Set AUTHED_PROVIDER_ID environment variable"
            )

        # Load or generate keys
        if key_file:
            with open(key_file, 'r') as f:
                keys = json.load(f)
            dpop_public_key = keys['public_key']
            click.echo(click.style("→", fg="blue") + f" Using existing keys from {click.style(key_file, fg='bright_black')}")
        else:
            # Generate new keys
            from ..commands.keys import generate_keypair
            public_key, private_key = generate_keypair()
            dpop_public_key = public_key
            
            # Save keys
            keys_file = f"agent_keys_{name or 'new'}.json"
            with open(keys_file, 'w') as f:
                json.dump({
                    "public_key": public_key,
                    "private_key": private_key
                }, f, indent=2)
            click.echo(click.style("✓", fg="green") + f" Generated new keys and saved to {click.style(keys_file, fg='blue')}")
        
        # Register agent
        response = await ctx.obj['auth'].request(
            'POST',
            '/agents/register',
            json={
                "provider_id": effective_provider_id,
                "name": name,
                "dpop_public_key": dpop_public_key
            }
        )
        
        if response.status_code == 401:
            raise click.UsageError("Authentication failed")
        elif response.status_code != 200:
            error_detail = response.text
            try:
                error_json = response.json()
                if 'detail' in error_json:
                    error_detail = error_json['detail']
            except:
                pass
            raise click.UsageError(f"Error: {error_detail}")
            
        try:
            result = response.json()
            click.echo("\n" + "=" * 60)
            click.echo(click.style("Agent Created Successfully", fg="green", bold=True))
            click.echo("=" * 60 + "\n")
            
            click.echo(f"{click.style('ID:', bold=True)}        {click.style(result.get('agent_id', 'N/A'), fg='yellow')}")
            click.echo(f"{click.style('Name:', bold=True)}      {click.style(name or 'N/A', fg='blue')}")
            click.echo(f"{click.style('Provider:', bold=True)}  {click.style(effective_provider_id, fg='magenta')}")
            
            click.echo("\n" + click.style("⚠️  Credentials (Store Securely)", fg="yellow", bold=True))
            click.echo("-" * 60)
            click.echo(f"Agent Secret:        {click.style(result.get('agent_secret', 'N/A'), fg='bright_black')}")
            click.echo(f"Registry Public Key: {click.style(result.get('registry_public_key', 'N/A'), fg='bright_black')}")
            click.echo()
            
            # Only print debug info if debug flag is set
            if ctx.obj.get('debug', False):
                click.echo(click.style("\n⚠️  Warning:", fg="yellow", bold=True))
                click.echo(f"Response status: {response.status_code}")
                click.echo(f"Response body: {response.text}")
        except Exception as e:
            click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1)

@group.command(name='delete')
@click.argument('agent-id')
@click.option('--force', is_flag=True, help='Force deletion without confirmation')
@click.pass_context
@async_command
async def delete_agent(ctx, agent_id: str, force: bool):
    """Delete an agent."""
    if not force:
        click.echo("\n" + click.style("⚠️  Warning:", fg="yellow", bold=True))
        click.echo(f"About to delete agent: {click.style(agent_id, fg='blue')}")
        click.echo(click.style("This action cannot be undone!", fg="yellow"))
        click.echo()
        
        if not click.confirm(click.style("Are you sure?", fg="yellow", bold=True)):
            ctx.exit(0)
    
    try:
        response = await ctx.obj['auth'].request(
            'DELETE',
            f'/agents/delete',
            params={'agent_id': agent_id}
        )
        
        if response.status_code == 401:
            raise click.UsageError("Authentication failed")
        elif response.status_code == 404:
            click.echo(click.style("✗", fg="red", bold=True) + f" Agent {click.style(agent_id, fg='blue')} not found", err=True)
            ctx.exit(1)
        elif response.status_code != 200:
            raise click.UsageError(f"Error: {response.text}")
            
        click.echo("\n" + click.style("✓", fg="green", bold=True) + 
                  f" Agent {click.style(agent_id, fg='blue')} deleted successfully\n")
            
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1)

@group.command(name='info')
@click.argument('agent-id')
@click.pass_context
@async_command
async def agent_info(ctx, agent_id: str):
    """Get detailed information about an agent."""
    try:
        response = await ctx.obj['auth'].request(
            'GET',
            f'/agents/{agent_id}'
        )
        
        if response.status_code == 401:
            raise click.UsageError("Authentication failed")
        elif response.status_code == 404:
            click.echo(click.style("✗", fg="red", bold=True) + f" Agent {click.style(agent_id, fg='blue')} not found", err=True)
            ctx.exit(1)
        elif response.status_code != 200:
            raise click.UsageError(f"Error: {response.text}")
            
        agent = response.json()
        
        click.echo("\n" + "=" * 60)
        click.echo(click.style("Agent Details", fg="blue", bold=True))
        click.echo("=" * 60 + "\n")
        
        click.echo(f"{click.style('Name:', bold=True)}      {click.style(agent.get('name', 'N/A'), fg='blue')}")
        click.echo(f"{click.style('ID:', bold=True)}        {click.style(agent['agent_id'], fg='yellow')}")
        click.echo(f"{click.style('Provider:', bold=True)}  {click.style(agent['provider_id'], fg='magenta')}")
        click.echo(f"{click.style('Created:', bold=True)}   {click.style(agent['created_at'], fg='bright_black')}")
        if agent.get('updated_at'):
            click.echo(f"{click.style('Updated:', bold=True)}   {click.style(agent['updated_at'], fg='bright_black')}")
            
        if agent.get('permissions'):
            click.echo(f"\n{click.style('Permissions:', bold=True)}")
            for perm in agent['permissions']:
                perm_type = click.style("AGENT", fg="cyan") if perm['type'] == 'allow_agent' else click.style("PROVIDER", fg="magenta")
                click.echo(f"  • {perm_type} → {click.style(perm['target_id'], fg='yellow')}")
        
        click.echo()
                
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1) 