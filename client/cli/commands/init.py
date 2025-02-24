"""Initialization and configuration commands."""

import click
import json
from pathlib import Path
import os
from typing import Optional

CONFIG_DIR = Path.home() / '.authed'
CONFIG_FILE = CONFIG_DIR / 'config.json'

@click.group(name='init')
def group():
    """Initialize and configure the CLI."""
    pass

@group.command(name='config')
@click.option('--registry-url', help='Registry URL to save in config')
@click.option('--provider-id', help='Provider ID to save in config')
@click.option('--provider-secret', help='Provider secret to save in config')
def configure(
    registry_url: Optional[str] = None,
    provider_id: Optional[str] = None,
    provider_secret: Optional[str] = None
):
    """Configure CLI credentials interactively or via arguments."""
    # Create config directory if it doesn't exist
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load existing config if it exists
    config = {}
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open('r') as f:
            config = json.load(f)
    
    # If no arguments provided, use interactive mode
    if not any([registry_url, provider_id, provider_secret]):
        click.echo("\n" + "=" * 60)
        click.echo(click.style("Interactive Configuration", fg="blue", bold=True))
        click.echo("=" * 60 + "\n")
        
        # Registry URL
        default_url = config.get('registry_url', '')
        registry_url = click.prompt(
            click.style("Registry URL", bold=True),
            default=default_url,
            type=str
        )
        
        # Provider ID
        default_id = config.get('provider_id', '')
        provider_id = click.prompt(
            click.style("Provider ID", bold=True),
            default=default_id,
            type=str
        )
        
        # Provider Secret
        default_secret = config.get('provider_secret', '')
        if default_secret:
            default_display = '*' * len(default_secret)
            click.echo(f"\nCurrent provider secret: {click.style(default_display, fg='bright_black')}")
            if not click.confirm(click.style("Update provider secret?", fg="yellow", bold=True), default=False):
                provider_secret = default_secret
            else:
                provider_secret = click.prompt(
                    click.style("Provider Secret", bold=True),
                    hide_input=True,
                    confirmation_prompt=True
                )
        else:
            provider_secret = click.prompt(
                click.style("Provider Secret", bold=True),
                hide_input=True,
                confirmation_prompt=True
            )
    
    # Update config
    config.update({
        'registry_url': registry_url,
        'provider_id': provider_id,
        'provider_secret': provider_secret
    })
    
    # Save config
    with CONFIG_FILE.open('w') as f:
        json.dump(config, f, indent=2)
    
    # Print success message
    click.echo("\n" + "=" * 60)
    click.echo(click.style("✓", fg="green", bold=True) + " Configuration saved successfully")
    click.echo("=" * 60)
    click.echo(f"\nConfig file: {click.style(str(CONFIG_FILE), fg='blue')}")
    click.echo("\nYou can now use the CLI in the following ways:")
    click.echo("\n1. " + click.style("Without credentials", bold=True) + ":")
    click.echo(click.style("   authed agents list", fg="bright_black"))
    click.echo("\n2. " + click.style("Override saved config", bold=True) + ":")
    click.echo(click.style("   authed --registry-url=URL --provider-id=ID --provider-secret=SECRET agents list", fg="bright_black"))
    click.echo()

@group.command(name='show')
def show_config():
    """Show current configuration."""
    if not CONFIG_FILE.exists():
        click.echo("\n" + click.style("⚠️  No configuration found", fg="yellow", bold=True))
        click.echo("Run " + click.style("authed init config", fg="blue", bold=True) + " to configure.")
        click.echo()
        return
    
    with CONFIG_FILE.open('r') as f:
        config = json.load(f)
    
    click.echo("\n" + "=" * 60)
    click.echo(click.style("Current Configuration", fg="blue", bold=True))
    click.echo("=" * 60 + "\n")
    
    # Registry URL
    click.echo(click.style("Registry URL:", bold=True))
    if url := config.get('registry_url'):
        click.echo(f"  {click.style(url, fg='bright_blue')}")
    else:
        click.echo(click.style("  Not set", fg="yellow", italic=True))
    
    # Provider ID
    click.echo(f"\n{click.style('Provider ID:', bold=True)}")
    if pid := config.get('provider_id'):
        click.echo(f"  {click.style(pid, fg='magenta')}")
    else:
        click.echo(click.style("  Not set", fg="yellow", italic=True))
    
    # Provider Secret
    click.echo(f"\n{click.style('Provider Secret:', bold=True)}")
    if config.get('provider_secret'):
        secret_display = '*' * len(config['provider_secret'])
        click.echo(f"  {click.style(secret_display, fg='bright_black')}")
    else:
        click.echo(click.style("  Not set", fg="yellow", italic=True))
    
    click.echo(f"\nConfig file: {click.style(str(CONFIG_FILE), fg='blue')}")
    click.echo()

@group.command(name='clear')
@click.option('--force', is_flag=True, help='Clear without confirmation')
def clear_config(force: bool):
    """Clear saved configuration."""
    if not CONFIG_FILE.exists():
        click.echo("\n" + click.style("⚠️  No configuration found", fg="yellow", bold=True))
        click.echo()
        return
    
    if not force:
        click.echo("\n" + click.style("⚠️  Warning", fg="yellow", bold=True))
        click.echo("You are about to clear all saved configuration.")
        click.echo(click.style("This action cannot be undone!", fg="yellow"))
        click.echo()
        
        if not click.confirm(click.style("Are you sure?", fg="yellow", bold=True)):
            click.echo(click.style("\nOperation cancelled", fg="bright_black", italic=True))
            click.echo()
            return
    
    CONFIG_FILE.unlink()
    click.echo("\n" + click.style("✓", fg="green", bold=True) + " Configuration cleared successfully")
    click.echo() 