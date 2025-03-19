"""Log streaming commands."""

import click
import json
from datetime import datetime
from typing import Optional
import websockets
from urllib.parse import urljoin, urlencode
from ..utils import async_command

@click.group(name='logs')
def group():
    """Stream and view logs."""
    pass

@group.command(name='stream')
@click.option('--provider-id', help='Filter logs by provider ID')
@click.option('--agent-id', help='Filter logs by agent ID')
@click.option('--level', type=click.Choice(['INFO', 'WARNING', 'ERROR']), help='Filter by log level')
@click.option('--event-type', help='Filter by event type')
@click.option('--output', type=click.Path(dir_okay=False), help='Save logs to file')
@click.pass_context
@async_command
async def stream_logs(
    ctx,
    provider_id: Optional[str],
    agent_id: Optional[str],
    level: Optional[str],
    event_type: Optional[str],
    output: Optional[str]
):
    """Stream logs in real-time.
    
    Connects to the registry's WebSocket endpoint to receive logs as they occur.
    Use filters to narrow down the logs you want to see.
    """
    try:
        # Build query parameters
        params = {}
        if provider_id:
            params['provider_id'] = provider_id
        if agent_id:
            params['agent_id'] = agent_id
        if level:
            params['level'] = level
        if event_type:
            params['event_type'] = event_type
            
        # Build WebSocket URL
        query = urlencode(params)
        base_url = ctx.obj['auth'].registry_url
        if base_url.startswith('http'):
            base_url = 'ws' + base_url[4:]
        ws_url = urljoin(base_url, '/logs/ws')
        if query:
            ws_url = f"{ws_url}?{query}"
        
        # Get auth headers
        headers = ctx.obj['auth'].get_headers()
        
        # Open output file if specified
        output_file = None
        if output:
            output_file = open(output, 'a')
            click.echo(click.style("✓", fg="green", bold=True) + f" Saving logs to {click.style(output, fg='blue')}")
        
        # Print header
        click.echo("\n" + "=" * 60)
        click.echo(click.style("Live Log Stream", fg="blue", bold=True))
        if provider_id:
            click.echo(f"Provider: {click.style(provider_id, fg='magenta')}")
        if agent_id:
            click.echo(f"Agent:    {click.style(agent_id, fg='yellow')}")
        if level:
            click.echo(f"Level:    {click.style(level, fg='cyan')}")
        if event_type:
            click.echo(f"Event:    {click.style(event_type, fg='bright_blue')}")
        click.echo("=" * 60)
        click.echo(click.style("\nConnecting to log stream...", fg="bright_black", italic=True))
        
        async with websockets.connect(
            ws_url,
            additional_headers=headers
        ) as websocket:
            click.echo(click.style("✓", fg="green", bold=True) + " Connected to log stream")
            click.echo(click.style("Press Ctrl+C to stop streaming\n", fg="bright_black"))
            
            while True:
                try:
                    message = await websocket.recv()
                    logs = json.loads(message)
                    
                    # Handle both single log and array of logs
                    if not isinstance(logs, list):
                        logs = [logs]
                    
                    for log in logs:
                        try:
                            # Format timestamp
                            timestamp = datetime.fromisoformat(log.get('timestamp', ''))
                            formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                            
                            # Format and colorize output
                            level_colors = {
                                'DEBUG': 'bright_black',
                                'INFO': 'green',
                                'WARNING': 'yellow',
                                'ERROR': 'red'
                            }
                            level_str = log.get('level', 'UNKNOWN')
                            level_color = level_colors.get(level_str, 'white')
                            
                            # Build the log line
                            log_line = [
                                click.style(formatted_time, fg='bright_black'),
                                f"[{click.style(level_str, fg=level_color, bold=True)}]"
                            ]
                            
                            # Add event type if present
                            if event_type := log.get('event_type'):
                                log_line.append(click.style(event_type, fg='bright_blue'))
                                
                            # Print the main log line
                            click.echo(" ".join(log_line))
                            
                            # Print details if present
                            if details := log.get('details'):
                                if isinstance(details, dict):
                                    # Print each detail on a new line
                                    for key, value in details.items():
                                        if key in ['agent_id', 'target_agent_id']:
                                            value = click.style(str(value), fg='yellow')
                                        elif key in ['provider_id']:
                                            value = click.style(str(value), fg='magenta')
                                        click.echo(f"  {click.style(key + ':', bold=True)} {value}")
                                else:
                                    click.echo(f"  {details}")
                                    
                            # Add separator between logs
                            click.echo(click.style("-" * 60, fg="bright_black"))
                            
                            # Save to file if specified
                            if output_file:
                                output_file.write(f"{formatted_time} [{level_str}] {event_type or ''}\n")
                                if details:
                                    output_file.write(f"Details: {json.dumps(details, indent=2)}\n")
                                output_file.write("-" * 60 + "\n")
                                output_file.flush()
                                
                        except Exception as e:
                            click.echo(click.style("✗", fg="red", bold=True) + f" Error processing log: {str(e)}", err=True)
                            continue
                        
                except websockets.exceptions.ConnectionClosed:
                    click.echo(click.style("\n⚠️  Connection closed by server", fg="yellow", bold=True))
                    break
                except json.JSONDecodeError as e:
                    click.echo(click.style("✗", fg="red", bold=True) + f" Error decoding message: {str(e)}", err=True)
                    continue
                    
    except KeyboardInterrupt:
        click.echo(click.style("\n✓", fg="green", bold=True) + " Stream disconnected by user")
    except Exception as e:
        click.echo(click.style("\n✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1)
    finally:
        if output_file:
            output_file.close()

@group.command(name='fetch')
@click.option('--provider-id', help='Filter logs by provider ID')
@click.option('--agent-id', help='Filter logs by agent ID')
@click.option('--level', type=click.Choice(['INFO', 'WARNING', 'ERROR']), help='Filter by log level')
@click.option('--event-type', help='Filter by event type')
@click.option('--from-date', help='Filter logs from this date (ISO format)')
@click.option('--limit', type=int, default=100, help='Maximum number of logs to fetch')
@click.option('--output', type=click.Path(dir_okay=False), help='Save logs to file')
@click.pass_context
@async_command
async def fetch_logs(
    ctx,
    provider_id: Optional[str],
    agent_id: Optional[str],
    level: Optional[str],
    event_type: Optional[str],
    from_date: Optional[str],
    limit: int,
    output: Optional[str]
):
    """Fetch historical logs.
    
    Retrieves logs from the registry's database based on specified filters.
    """
    try:
        # Build query parameters
        params = {}
        if provider_id:
            params['provider_id'] = provider_id
        if agent_id:
            params['agent_id'] = agent_id
        if level:
            params['level'] = level
        if event_type:
            params['event_type'] = event_type
        if from_date:
            params['from_date'] = from_date
        params['limit'] = str(limit)
        
        response = await ctx.obj['auth'].request(
            'GET',
            '/logs',
            params=params
        )
        
        if response.status_code == 401:
            raise click.UsageError("Authentication failed")
        elif response.status_code != 200:
            raise click.UsageError(f"Error: {response.text}")
            
        logs = response.json()
        
        if output:
            # Save to file
            with open(output, 'w') as f:
                json.dump(logs, f, indent=2)
            click.echo(click.style("✓", fg="green", bold=True) + f" Logs saved to {click.style(output, fg='blue')}")
        else:
            # Print header
            click.echo("\n" + "=" * 60)
            click.echo(click.style("Historical Logs", fg="blue", bold=True))
            if provider_id:
                click.echo(f"Provider: {click.style(provider_id, fg='magenta')}")
            if agent_id:
                click.echo(f"Agent:    {click.style(agent_id, fg='yellow')}")
            if level:
                click.echo(f"Level:    {click.style(level, fg='cyan')}")
            if event_type:
                click.echo(f"Event:    {click.style(event_type, fg='bright_blue')}")
            if from_date:
                click.echo(f"From:     {click.style(from_date, fg='bright_black')}")
            click.echo(f"Limit:    {click.style(str(limit), fg='bright_black')}")
            click.echo("=" * 60)
            
            if not logs:
                click.echo(click.style("\nNo logs found", fg="yellow", italic=True))
                click.echo()
                return
                
            # Print logs
            for log in logs:
                timestamp = datetime.fromisoformat(log['timestamp'])
                formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                
                level_colors = {
                    'DEBUG': 'bright_black',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red'
                }
                level_str = log['level']
                level_color = level_colors.get(level_str, 'white')
                
                # Print main log line
                log_line = [
                    click.style(formatted_time, fg='bright_black'),
                    f"[{click.style(level_str, fg=level_color, bold=True)}]"
                ]
                
                if event_type := log.get('event_type'):
                    log_line.append(click.style(event_type, fg='bright_blue'))
                    
                click.echo("\n" + " ".join(log_line))
                
                # Print details if present
                if details := log.get('details'):
                    if isinstance(details, dict):
                        for key, value in details.items():
                            if key in ['agent_id', 'target_agent_id']:
                                value = click.style(str(value), fg='yellow')
                            elif key in ['provider_id']:
                                value = click.style(str(value), fg='magenta')
                            click.echo(f"  {click.style(key + ':', bold=True)} {value}")
                    else:
                        click.echo(f"  {details}")
                        
                click.echo(click.style("-" * 60, fg="bright_black"))
                
            click.echo()
                
    except Exception as e:
        click.echo(click.style("✗ Error: ", fg="red", bold=True) + str(e), err=True)
        ctx.exit(1) 