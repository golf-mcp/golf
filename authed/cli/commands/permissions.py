"""Permission management commands."""

import click
import json
from pathlib import Path
from typing import Optional
from ..utils import async_command

@click.group(name='permissions')
def group():
    """Manage agent permissions."""
    pass

@group.command(name='list')
@click.argument('agent-id')
@click.option('--output', type=click.Path(dir_okay=False), help='Save output to JSON file')
@click.pass_context
@async_command
async def list_permissions(ctx, agent_id: str, output: Optional[str]):
    """List permissions for an agent."""
    try:
        response = await ctx.obj['auth'].request(
            'GET',
            f'/agents/{agent_id}/permissions'
        )
        
        if response.status_code == 401:
            raise click.UsageError("Authentication failed")
        elif response.status_code == 404:
            click.echo(click.style("✗", fg="red", bold=True) + f" Agent {click.style(agent_id, fg='blue')} not found", err=True)
            ctx.exit(1)
        elif response.status_code != 200:
            raise click.UsageError(f"Error: {response.text}")
            
        data = response.json()
        
        if output:
            # Save to file
            output_path = Path(output)
            with output_path.open('w') as f:
                json.dump(data['permissions'], f, indent=2)
            click.echo(click.style("✓", fg="green") + f" Permissions saved to {click.style(output, fg='blue')}")
        else:
            # Print to console
            click.echo("\n" + "=" * 60)
            click.echo(click.style("Permissions", fg="blue", bold=True) + " for agent: " + 
                      click.style(agent_id, fg="yellow"))
            click.echo("=" * 60)
            
            if data['permissions']:
                for perm in data['permissions']:
                    perm_type = perm['type']
                    target = perm['target_id']
                    
                    # Color-code different permission types
                    if perm_type == 'allow_agent':
                        type_str = click.style("AGENT", fg="cyan")
                    else:
                        type_str = click.style("PROVIDER", fg="magenta")
                        
                    click.echo(f"\n• {type_str} → {click.style(target, fg='yellow')}")
            else:
                click.echo("\n" + click.style("No permissions set", fg="yellow", italic=True))
            
            click.echo("\n" + "=" * 60 + "\n")
                
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1)

@group.command(name='grant')
@click.argument('agent-id')
@click.option('--type', 'perm_type', type=click.Choice(['allow_agent', 'allow_provider']), required=True,
          help='Type of permission to grant')
@click.option('--target-id', required=True, help='ID of the target agent or provider')
@click.pass_context
@async_command
async def grant_permission(ctx, agent_id: str, perm_type: str, target_id: str):
    """Grant a permission to an agent."""
    try:
        response = await ctx.obj['auth'].request(
            'PATCH',
            f'/agents/{agent_id}/permissions',
            json={
                "add": [{
                    "type": perm_type,
                    "target_id": target_id
                }]
            }
        )
        
        if response.status_code == 401:
            raise click.UsageError("Authentication failed")
        elif response.status_code == 404:
            click.echo(click.style("✗", fg="red", bold=True) + f" Agent {click.style(agent_id, fg='blue')} not found", err=True)
            ctx.exit(1)
        elif response.status_code != 200:
            raise click.UsageError(f"Error: {response.text}")
            
        # Format success message
        type_str = click.style("AGENT", fg="cyan") if perm_type == 'allow_agent' else click.style("PROVIDER", fg="magenta")
        click.echo("\n" + "=" * 60)
        click.echo(click.style("Permission Granted", fg="green", bold=True))
        click.echo("=" * 60 + "\n")
        click.echo(f"{click.style('Agent:', bold=True)}   {click.style(agent_id, fg='blue')}")
        click.echo(f"{click.style('Type:', bold=True)}    {type_str}")
        click.echo(f"{click.style('Target:', bold=True)}  {click.style(target_id, fg='yellow')}\n")
        
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1)

@group.command(name='revoke')
@click.argument('agent-id')
@click.option('--type', 'perm_type', type=click.Choice(['allow_agent', 'allow_provider']), required=True,
          help='Type of permission to revoke')
@click.option('--target-id', required=True, help='ID of the target agent or provider')
@click.option('--force', is_flag=True, help='Force revocation without confirmation')
@click.pass_context
@async_command
async def revoke_permission(ctx, agent_id: str, perm_type: str, target_id: str, force: bool):
    """Revoke a permission from an agent."""
    if not force:
        type_str = click.style("AGENT", fg="cyan") if perm_type == 'allow_agent' else click.style("PROVIDER", fg="magenta")
        click.echo("\n" + click.style("⚠️  Warning:", fg="yellow", bold=True))
        click.echo("About to revoke permission:")
        click.echo(f"{click.style('Agent:', bold=True)}   {click.style(agent_id, fg='blue')}")
        click.echo(f"{click.style('Type:', bold=True)}    {type_str}")
        click.echo(f"{click.style('Target:', bold=True)}  {click.style(target_id, fg='yellow')}\n")
        
        if not click.confirm(click.style("Are you sure?", fg="yellow", bold=True)):
            ctx.exit(0)
            
    try:
        response = await ctx.obj['auth'].request(
            'PATCH',
            f'/agents/{agent_id}/permissions',
            json={
                "remove": [{
                    "type": perm_type,
                    "target_id": target_id
                }]
            }
        )
        
        if response.status_code == 401:
            raise click.UsageError("Authentication failed")
        elif response.status_code == 404:
            click.echo(click.style("✗", fg="red", bold=True) + f" Agent {click.style(agent_id, fg='blue')} not found", err=True)
            ctx.exit(1)
        elif response.status_code != 200:
            raise click.UsageError(f"Error: {response.text}")
            
        click.echo("\n" + click.style("✓", fg="green", bold=True) + " Permission revoked successfully\n")
        
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1)

@group.command(name='clear')
@click.argument('agent-id')
@click.option('--force', is_flag=True, help='Force clearing without confirmation')
@click.pass_context
@async_command
async def clear_permissions(ctx, agent_id: str, force: bool):
    """Clear all permissions for an agent."""
    if not force:
        click.echo("\n" + click.style("⚠️  Warning:", fg="yellow", bold=True))
        click.echo("About to clear all permissions for agent:")
        click.echo(click.style(agent_id, fg='blue', bold=True))
        click.echo(click.style("\nThis action cannot be undone!", fg="yellow"))
        click.echo()
        
        if not click.confirm(click.style("Are you sure?", fg="yellow", bold=True)):
            ctx.exit(0)
            
    try:
        response = await ctx.obj['auth'].request(
            'PUT',
            f'/agents/{agent_id}/permissions',
            json=[]
        )
        
        if response.status_code == 401:
            raise click.UsageError("Authentication failed")
        elif response.status_code == 404:
            click.echo(click.style("✗", fg="red", bold=True) + f" Agent {click.style(agent_id, fg='blue')} not found", err=True)
            ctx.exit(1)
        elif response.status_code != 200:
            raise click.UsageError(f"Error: {response.text}")
            
        click.echo("\n" + click.style("✓", fg="green", bold=True) + 
                  f" All permissions cleared for agent: {click.style(agent_id, fg='blue')}\n")
        
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1) 