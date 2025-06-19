"""Metrics integration for the GolfMCP build process.

This module provides functions for generating Prometheus metrics initialization
and collection code for FastMCP servers built with GolfMCP.
"""


def generate_metrics_imports() -> list[str]:
    """Generate import statements for metrics collection.

    Returns:
        List of import statements for metrics
    """
    return [
        "# Prometheus metrics imports",
        "from golf.metrics import init_metrics, get_metrics_collector",
        "from prometheus_client import generate_latest, CONTENT_TYPE_LATEST",
        "from starlette.responses import Response",
    ]


def generate_metrics_initialization(server_name: str) -> list[str]:
    """Generate metrics initialization code.
    
    Args:
        server_name: Name of the MCP server
        
    Returns:
        List of code lines for metrics initialization
    """
    return [
        "# Initialize metrics collection",
        "init_metrics(enabled=True)",
        "",
    ]


def generate_metrics_route(metrics_path: str) -> list[str]:
    """Generate the metrics endpoint route code.
    
    Args:
        metrics_path: Path for the metrics endpoint (e.g., "/metrics")
        
    Returns:
        List of code lines for the metrics route
    """
    return [
        f"# Add metrics endpoint",
        f'@mcp.custom_route("{metrics_path}", methods=["GET"])',
        "async def metrics_endpoint(request):",
        '    """Prometheus metrics endpoint for monitoring."""',
        "    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)",
        "",
    ]


def get_metrics_dependencies() -> list[str]:
    """Get list of metrics dependencies to add to pyproject.toml.

    Returns:
        List of package requirements strings
    """
    return [
        "prometheus-client>=0.19.0",
    ] 