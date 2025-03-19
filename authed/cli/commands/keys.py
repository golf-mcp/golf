"""Key management commands."""

import click
import json
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from typing import Optional
def generate_keypair() -> tuple[str, str]:
    """Generate a new RSA keypair.
    
    Returns:
        tuple[str, str]: (public_key_pem, private_key_pem)
    """
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # Get public key
    public_key = private_key.public_key()
    
    # Convert to PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    return public_pem, private_pem

@click.group(name='keys')
def group():
    """Manage keys."""
    pass

@group.command(name='generate')
@click.option('--output', type=click.Path(dir_okay=False), help='Output file path')
@click.pass_context
def generate_keys(ctx, output: Optional[str]):
    """Generate a new keypair."""
    try:
        public_key, private_key = generate_keypair()
        
        # Format keys for output
        keys = {
            "public_key": public_key,
            "private_key": private_key
        }
        
        if output:
            # Save to file
            output_path = Path(output)
            with output_path.open('w') as f:
                json.dump(keys, f, indent=2)
            click.echo(click.style("✓", fg="green", bold=True) + f" Keys saved to {click.style(output, fg='blue')}")
        else:
            # Print to console
            click.echo("\n" + "=" * 60)
            click.echo(click.style("Generated Keys", fg="blue", bold=True))
            click.echo("=" * 60 + "\n")
            
            click.echo(click.style("Public Key:", bold=True))
            click.echo(click.style(public_key, fg="bright_black"))
            
            click.echo("\n" + click.style("Private Key:", bold=True) + click.style(" (Keep this secure!)", fg="yellow"))
            click.echo(click.style(private_key, fg="bright_black"))
            click.echo()
            
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1)

@group.command(name='show-public')
@click.argument('key-file', type=click.Path(exists=True))
@click.pass_context
def show_public_key(ctx, key_file: str):
    """Show the public key from a key file."""
    try:
        with open(key_file, 'r') as f:
            keys = json.load(f)
            
        if 'public_key' not in keys:
            raise click.UsageError("Key file does not contain a public key")
            
        click.echo("\n" + "=" * 60)
        click.echo(click.style("Public Key", fg="blue", bold=True) + 
                  f" from {click.style(key_file, fg='bright_black')}")
        click.echo("=" * 60 + "\n")
        click.echo(click.style(keys['public_key'], fg="bright_black"))
        click.echo()
            
    except json.JSONDecodeError:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + "Invalid JSON in key file", err=True)
        ctx.exit(1)
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1)

@group.command(name='show-private')
@click.argument('key-file', type=click.Path(exists=True))
@click.option('--force', is_flag=True, help='Show private key without confirmation')
@click.pass_context
def show_private_key(ctx, key_file: str, force: bool):
    """Show the private key from a key file."""
    if not force:
        click.echo("\n" + click.style("⚠️  Warning:", fg="yellow", bold=True))
        click.echo("You are about to display a private key.")
        click.echo(click.style("This should only be done in a secure environment!", fg="yellow"))
        click.echo()
        
        if not click.confirm(click.style("Are you sure?", fg="yellow", bold=True)):
            ctx.exit(0)
    
    try:
        with open(key_file, 'r') as f:
            keys = json.load(f)
            
        if 'private_key' not in keys:
            raise click.UsageError("Key file does not contain a private key")
            
        click.echo("\n" + "=" * 60)
        click.echo(click.style("Private Key", fg="blue", bold=True) + 
                  f" from {click.style(key_file, fg='bright_black')}")
        click.echo(click.style("Keep this secure and never share it!", fg="yellow", bold=True))
        click.echo("=" * 60 + "\n")
        click.echo(click.style(keys['private_key'], fg="bright_black"))
        click.echo()
            
    except json.JSONDecodeError:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + "Invalid JSON in key file", err=True)
        ctx.exit(1)
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1) 