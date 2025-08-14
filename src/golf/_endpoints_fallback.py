"""Fallback endpoints for development/editable installs."""

import os

# These are used when the generated _endpoints.py doesn't exist (dev mode)
# or when environment variables override the built-in values

PLATFORM_API_URL = os.getenv("GOLF_PLATFORM_API_URL", "http://localhost:8000/api/resources")

OTEL_ENDPOINT = os.getenv("GOLF_OTEL_ENDPOINT", "http://localhost:4318/v1/traces")
