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
        "from starlette.middleware.base import BaseHTTPMiddleware",
        "from starlette.requests import Request",
        "import time",
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
        "# Add metrics endpoint",
        f'@mcp.custom_route("{metrics_path}", methods=["GET"])',
        "async def metrics_endpoint(request):",
        '    """Prometheus metrics endpoint for monitoring."""',
        "    # Update uptime before returning metrics",
        "    update_uptime()",
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


def generate_metrics_instrumentation() -> list[str]:
    """Generate metrics instrumentation wrapper functions.

    Returns:
        List of code lines for metrics instrumentation
    """
    return [
        "# Metrics instrumentation wrapper functions",
        "import time",
        "import functools",
        "from typing import Any, Callable",
        "",
        "def instrument_tool(func: Callable, tool_name: str) -> Callable:",
        '    """Wrap a tool function with metrics collection."""',
        "    @functools.wraps(func)",
        "    async def wrapper(*args, **kwargs) -> Any:",
        "        collector = get_metrics_collector()",
        "        start_time = time.time()",
        "        status = 'success'",
        "        try:",
        "            result = await func(*args, **kwargs)",
        "            return result",
        "        except Exception as e:",
        "            status = 'error'",
        "            collector.increment_error('tool', type(e).__name__)",
        "            raise",
        "        finally:",
        "            duration = time.time() - start_time",
        "            collector.increment_tool_execution(tool_name, status)",
        "            collector.record_tool_duration(tool_name, duration)",
        "    return wrapper",
        "",
        "def instrument_resource(func: Callable, resource_name: str) -> Callable:",
        '    """Wrap a resource function with metrics collection."""',
        "    @functools.wraps(func)",
        "    async def wrapper(*args, **kwargs) -> Any:",
        "        collector = get_metrics_collector()",
        "        try:",
        "            result = await func(*args, **kwargs)",
        "            # Extract URI from args if available for resource_reads metric",
        "            if args and len(args) > 0:",
        "                uri = str(args[0]) if args[0] else resource_name",
        "            else:",
        "                uri = resource_name",
        "            collector.increment_resource_read(uri)",
        "            return result",
        "        except Exception as e:",
        "            collector.increment_error('resource', type(e).__name__)",
        "            raise",
        "    return wrapper",
        "",
        "def instrument_prompt(func: Callable, prompt_name: str) -> Callable:",
        '    """Wrap a prompt function with metrics collection."""',
        "    @functools.wraps(func)",
        "    async def wrapper(*args, **kwargs) -> Any:",
        "        collector = get_metrics_collector()",
        "        try:",
        "            result = await func(*args, **kwargs)",
        "            collector.increment_prompt_generation(prompt_name)",
        "            return result",
        "        except Exception as e:",
        "            collector.increment_error('prompt', type(e).__name__)",
        "            raise",
        "    return wrapper",
        "",
        "# HTTP Request Metrics Middleware",
        "class MetricsMiddleware(BaseHTTPMiddleware):",
        '    """Middleware to collect HTTP request metrics."""',
        "",
        "    async def dispatch(self, request: Request, call_next):",
        "        collector = get_metrics_collector()",
        "        start_time = time.time()",
        "        ",
        "        # Extract path and method",
        "        method = request.method",
        "        path = request.url.path",
        "        ",
        "        try:",
        "            response = await call_next(request)",
        "            status_code = response.status_code",
        "        except Exception as e:",
        "            status_code = 500",
        "            collector.increment_error('http', type(e).__name__)",
        "            raise",
        "        finally:",
        "            duration = time.time() - start_time",
        "            collector.increment_http_request(method, status_code, path)",
        "            collector.record_http_duration(method, path, duration)",
        "        ",
        "        return response",
        "",
        "# Session tracking helpers",
        "import atexit",
        "from contextlib import asynccontextmanager",
        "",
        "# Global server start time for uptime tracking",
        "_server_start_time = time.time()",
        "",
        "def track_session_start():",
        '    """Track when a new session starts."""',
        "    collector = get_metrics_collector()",
        "    collector.increment_session()",
        "",
        "def track_session_end(start_time: float):",
        '    """Track when a session ends."""',
        "    collector = get_metrics_collector()",
        "    duration = time.time() - start_time",
        "    collector.record_session_duration(duration)",
        "",
        "def update_uptime():",
        '    """Update the uptime metric."""',
        "    collector = get_metrics_collector()",
        "    uptime = time.time() - _server_start_time",
        "    collector.set_uptime(uptime)",
        "",
        "# Initialize uptime tracking",
        "update_uptime()",
        "",
    ]


def generate_session_tracking() -> list[str]:
    """Generate session tracking integration code.

    Returns:
        List of code lines for session tracking
    """
    return [
        "# Session tracking integration",
        "import asyncio",
        "from typing import Dict",
        "",
        "# Track active sessions",
        "_active_sessions: Dict[str, float] = {}",
        "",
        "# Hook into FastMCP's session lifecycle if available",
        "try:",
        "    from fastmcp.server import SessionManager",
        "    ",
        "    # Monkey patch session creation if possible",
        "    _original_create_session = getattr(mcp, '_create_session', None)",
        "    if _original_create_session:",
        "        async def _patched_create_session(*args, **kwargs):",
        "            session_id = str(id(args)) if args else 'unknown'",
        "            _active_sessions[session_id] = time.time()",
        "            track_session_start()",
        "            try:",
        "                return await _original_create_session(*args, **kwargs)",
        "            except Exception:",
        "                # If session creation fails, clean up",
        "                if session_id in _active_sessions:",
        "                    del _active_sessions[session_id]",
        "                raise",
        "        ",
        "        mcp._create_session = _patched_create_session",
        "except (ImportError, AttributeError):",
        "    # Fallback: track sessions via request patterns",
        "    pass",
        "",
    ]
