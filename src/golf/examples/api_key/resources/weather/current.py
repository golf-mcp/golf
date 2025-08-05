"""Current weather resource example."""

from datetime import datetime
from typing import Any

from .common import weather_client

# The URI that clients will use to access this resource
resource_uri = "weather://current/{city}"


async def current_weather(city: str) -> dict[str, Any]:
    """Provide current weather for the specified city.

    This example demonstrates:
    1. Nested resource organization (resources/weather/current.py)
    2. Dynamic URI parameters (city in this case)
    3. Using shared client from the common.py file
    """
    # Use the shared weather client from common.py
    weather_data = await weather_client.get_current(city)

    # Add some additional data
    weather_data.update(
        {
            "time": datetime.now().isoformat(),
            "source": "GolfMCP Weather API",
            "unit": "fahrenheit",
        }
    )

    return weather_data


# Designate the entry point function
export = current_weather
