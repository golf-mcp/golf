"""Metrics collector for Golf MCP servers."""

from typing import Optional

# Global metrics collector instance
_metrics_collector: Optional["MetricsCollector"] = None


class MetricsCollector:
    """Collects metrics for Golf MCP servers using Prometheus client."""

    def __init__(self, enabled: bool = False) -> None:
        """Initialize the metrics collector.

        Args:
            enabled: Whether metrics collection is enabled
        """
        self.enabled = enabled
        self._metrics = {}

        if self.enabled:
            self._init_prometheus_metrics()

    def _init_prometheus_metrics(self) -> None:
        """Initialize Prometheus metrics if enabled."""
        try:
            from prometheus_client import Counter, Histogram, Gauge

            # Tool execution metrics
            self._metrics["tool_executions"] = Counter(
                "golf_tool_executions_total",
                "Total number of tool executions",
                ["tool_name", "status"],
            )

            self._metrics["tool_duration"] = Histogram(
                "golf_tool_duration_seconds",
                "Tool execution duration in seconds",
                ["tool_name"],
            )

            # HTTP request metrics
            self._metrics["http_requests"] = Counter(
                "golf_http_requests_total",
                "Total number of HTTP requests",
                ["method", "status_code", "path"],
            )

            self._metrics["http_duration"] = Histogram(
                "golf_http_request_duration_seconds",
                "HTTP request duration in seconds",
                ["method", "path"],
            )

            # Resource access metrics
            self._metrics["resource_reads"] = Counter(
                "golf_resource_reads_total",
                "Total number of resource reads",
                ["resource_uri"],
            )

            # Prompt generation metrics
            self._metrics["prompt_generations"] = Counter(
                "golf_prompt_generations_total",
                "Total number of prompt generations",
                ["prompt_name"],
            )

            # Sampling metrics
            self._metrics["sampling_requests"] = Counter(
                "golf_sampling_requests_total",
                "Total number of sampling requests",
                ["sampling_type", "status"],
            )

            self._metrics["sampling_duration"] = Histogram(
                "golf_sampling_duration_seconds",
                "Sampling request duration in seconds",
                ["sampling_type"],
            )

            self._metrics["sampling_tokens"] = Histogram(
                "golf_sampling_tokens",
                "Number of tokens in sampling responses",
                ["sampling_type"],
            )

            # Elicitation metrics
            self._metrics["elicitation_requests"] = Counter(
                "golf_elicitation_requests_total",
                "Total number of elicitation requests",
                ["elicitation_type", "status"],
            )

            self._metrics["elicitation_duration"] = Histogram(
                "golf_elicitation_duration_seconds",
                "Elicitation request duration in seconds",
                ["elicitation_type"],
            )

            # Error metrics
            self._metrics["errors"] = Counter(
                "golf_errors_total",
                "Total number of errors",
                ["component_type", "error_type"],
            )

            # Session metrics
            self._metrics["sessions_total"] = Counter("golf_sessions_total", "Total number of sessions created")

            self._metrics["session_duration"] = Histogram(
                "golf_session_duration_seconds", "Session duration in seconds"
            )

            # System metrics
            self._metrics["uptime"] = Gauge("golf_uptime_seconds", "Server uptime in seconds")

        except ImportError:
            # Prometheus client not available, disable metrics
            self.enabled = False

    def increment_tool_execution(self, tool_name: str, status: str) -> None:
        """Record a tool execution.

        Args:
            tool_name: Name of the tool that was executed
            status: Execution status ('success' or 'error')
        """
        if not self.enabled or "tool_executions" not in self._metrics:
            return

        self._metrics["tool_executions"].labels(tool_name=tool_name, status=status).inc()

    def record_tool_duration(self, tool_name: str, duration: float) -> None:
        """Record tool execution duration.

        Args:
            tool_name: Name of the tool
            duration: Execution duration in seconds
        """
        if not self.enabled or "tool_duration" not in self._metrics:
            return

        self._metrics["tool_duration"].labels(tool_name=tool_name).observe(duration)

    def increment_http_request(self, method: str, status_code: int, path: str) -> None:
        """Record an HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            status_code: HTTP status code
            path: Request path
        """
        if not self.enabled or "http_requests" not in self._metrics:
            return

        self._metrics["http_requests"].labels(method=method, status_code=str(status_code), path=path).inc()

    def record_http_duration(self, method: str, path: str, duration: float) -> None:
        """Record HTTP request duration.

        Args:
            method: HTTP method
            path: Request path
            duration: Request duration in seconds
        """
        if not self.enabled or "http_duration" not in self._metrics:
            return

        self._metrics["http_duration"].labels(method=method, path=path).observe(duration)

    def increment_resource_read(self, resource_uri: str) -> None:
        """Record a resource read.

        Args:
            resource_uri: URI of the resource that was read
        """
        if not self.enabled or "resource_reads" not in self._metrics:
            return

        self._metrics["resource_reads"].labels(resource_uri=resource_uri).inc()

    def increment_prompt_generation(self, prompt_name: str) -> None:
        """Record a prompt generation.

        Args:
            prompt_name: Name of the prompt that was generated
        """
        if not self.enabled or "prompt_generations" not in self._metrics:
            return

        self._metrics["prompt_generations"].labels(prompt_name=prompt_name).inc()

    def increment_error(self, component_type: str, error_type: str) -> None:
        """Record an error.

        Args:
            component_type: Type of component ('tool', 'resource', 'prompt', 'http')
            error_type: Type of error ('timeout', 'auth_error',
                'validation_error', etc.)
        """
        if not self.enabled or "errors" not in self._metrics:
            return

        self._metrics["errors"].labels(component_type=component_type, error_type=error_type).inc()

    def increment_session(self) -> None:
        """Record a new session."""
        if not self.enabled or "sessions_total" not in self._metrics:
            return

        self._metrics["sessions_total"].inc()

    def record_session_duration(self, duration: float) -> None:
        """Record session duration.

        Args:
            duration: Session duration in seconds
        """
        if not self.enabled or "session_duration" not in self._metrics:
            return

        self._metrics["session_duration"].observe(duration)

    def set_uptime(self, seconds: float) -> None:
        """Set the server uptime.

        Args:
            seconds: Server uptime in seconds
        """
        if not self.enabled or "uptime" not in self._metrics:
            return

        self._metrics["uptime"].set(seconds)

    def increment_sampling(self, sampling_type: str, status: str) -> None:
        """Record a sampling request.

        Args:
            sampling_type: Type of sampling ('sample', 'structured', 'context')
            status: Request status ('success' or 'error')
        """
        if not self.enabled or "sampling_requests" not in self._metrics:
            return

        self._metrics["sampling_requests"].labels(sampling_type=sampling_type, status=status).inc()

    def record_sampling_duration(self, sampling_type: str, duration: float) -> None:
        """Record sampling request duration.

        Args:
            sampling_type: Type of sampling
            duration: Request duration in seconds
        """
        if not self.enabled or "sampling_duration" not in self._metrics:
            return

        self._metrics["sampling_duration"].labels(sampling_type=sampling_type).observe(duration)

    def record_sampling_tokens(self, sampling_type: str, token_count: int) -> None:
        """Record sampling token count.

        Args:
            sampling_type: Type of sampling
            token_count: Number of tokens in the response
        """
        if not self.enabled or "sampling_tokens" not in self._metrics:
            return

        self._metrics["sampling_tokens"].labels(sampling_type=sampling_type).observe(token_count)

    def increment_elicitation(self, elicitation_type: str, status: str) -> None:
        """Record an elicitation request.

        Args:
            elicitation_type: Type of elicitation ('elicit', 'confirmation')
            status: Request status ('success' or 'error')
        """
        if not self.enabled or "elicitation_requests" not in self._metrics:
            return

        self._metrics["elicitation_requests"].labels(elicitation_type=elicitation_type, status=status).inc()

    def record_elicitation_duration(self, elicitation_type: str, duration: float) -> None:
        """Record elicitation request duration.

        Args:
            elicitation_type: Type of elicitation
            duration: Request duration in seconds
        """
        if not self.enabled or "elicitation_duration" not in self._metrics:
            return

        self._metrics["elicitation_duration"].labels(elicitation_type=elicitation_type).observe(duration)


def init_metrics_collector(enabled: bool = False) -> MetricsCollector:
    """Initialize the global metrics collector.

    Args:
        enabled: Whether to enable metrics collection

    Returns:
        The initialized metrics collector
    """
    global _metrics_collector
    _metrics_collector = MetricsCollector(enabled=enabled)
    return _metrics_collector


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance.

    Returns:
        The metrics collector, or a disabled one if not initialized
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(enabled=False)
    return _metrics_collector
