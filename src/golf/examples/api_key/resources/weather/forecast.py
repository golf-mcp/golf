"""Weather forecast resource example demonstrating nested resources."""

from datetime import datetime
from typing import Any

from .common import weather_client

# The URI that clients will use to access this resource
resource_uri = "weather://forecast/{city}"


async def forecast_weather(city: str) -> dict[str, Any]:
    """Provide a weather forecast for the specified city.

    This example demonstrates:
    1. Nested resource organization (resources/weather/forecast.py)
    2. Dynamic URI parameters (city in this case)
    3. Using shared client from the common.py file
    """
    # Use the shared weather client from common.py
    forecast_data = await weather_client.get_forecast(city, days=5)

    # Add some additional data
    forecast_data.update(
        {
            "updated_at": datetime.now().isoformat(),
            "source": "GolfMCP Weather API",
            "unit": "fahrenheit",
        }
    )

    return forecast_data


# Designate the entry point function
export = forecast_weather
