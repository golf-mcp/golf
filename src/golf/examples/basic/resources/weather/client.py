"""Weather shared functionality.

This file demonstrates the recommended pattern for
sharing functionality across multiple resources in a directory.
Golf automatically discovers and includes shared Python files in builds.
"""

import os
from typing import Any

# Read configuration from environment variables
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "mock_key")
WEATHER_API_URL = os.environ.get("WEATHER_API_URL", "https://api.example.com/weather")
TEMPERATURE_UNIT = os.environ.get("WEATHER_TEMP_UNIT", "fahrenheit")


class WeatherApiClient:
    """Mock weather API client."""

    def __init__(self, api_key: str = WEATHER_API_KEY, api_url: str = WEATHER_API_URL) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.unit = TEMPERATURE_UNIT

    async def get_forecast(self, city: str, days: int = 3) -> dict[str, Any]:
        """Get weather forecast for a city (mock implementation)."""
        # This would make an API call in a real implementation
        return {
            "city": city,
            "unit": self.unit,
            "forecast": [{"day": i, "temp": 70 + i} for i in range(days)],
        }

    async def get_current(self, city: str) -> dict[str, Any]:
        """Get current weather for a city (mock implementation)."""
        return {
            "city": city,
            "unit": self.unit,
            "temperature": 72,
            "conditions": "Sunny",
        }


# Create a shared weather client that can be imported by all resources in this directory
weather_client = WeatherApiClient()

# This could also define shared models or other utilities
# that would be common across weather-related resources