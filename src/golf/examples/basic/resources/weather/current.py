"""Current weather resource example."""

from datetime import datetime
from typing import Any

from .client import weather_client

# The URI that clients will use to access this resource
resource_uri = "weather://current"


async def current_weather() -> dict[str, Any]:
    """Provide current weather for a default city.

    This example demonstrates:
    1. Nested resource organization (resources/weather/current.py)
    2. Resource without URI parameters
    3. Using shared client from the client.py file
    """
    # Use the shared weather client from client.py
    weather_data = await weather_client.get_current("New York")

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
