"""Golf metrics module for Prometheus-compatible metrics collection."""

from golf.metrics.collector import MetricsCollector, get_metrics_collector
from golf.metrics.registry import init_metrics

__all__ = [
    "MetricsCollector",
    "get_metrics_collector",
    "init_metrics",
]
