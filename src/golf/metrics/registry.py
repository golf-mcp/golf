"""Metrics registry for Golf MCP servers."""

from golf.metrics.collector import init_metrics_collector


def init_metrics(enabled: bool = False) -> None:
    """Initialize the metrics system.

    Args:
        enabled: Whether to enable metrics collection
    """
    init_metrics_collector(enabled=enabled)
