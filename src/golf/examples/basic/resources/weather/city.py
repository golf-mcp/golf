"""Weather resource template example with URI parameters."""

from datetime import datetime
from typing import Any

from .client import weather_client

# The URI template that clients will use to access this resource
# The {city} parameter makes this a resource template
resource_uri = "weather://city/{city}"


async def get_weather_for_city(city: str) -> dict[str, Any]:
    """Provide current weather for a specific city.

    This example demonstrates:
    1. Resource templates with URI parameters ({city})
    2. Dynamic resource access based on parameters
    3. Using shared client from the client.py file
    4. FastMCP 2.11+ ResourceTemplate.from_function() usage

    Args:
        city: The city name to get weather for

    Returns:
        Weather data for the specified city
    """
    # Use the shared weather client from client.py
    weather_data = await weather_client.get_current(city)

    # Add some additional data
    weather_data.update(
        {
            "city": city,
            "time": datetime.now().isoformat(),
            "source": "GolfMCP Weather API",
            "unit": "fahrenheit",
            "resource_type": "template",
        }
    )

    return weather_data


# Designate the entry point function
export = get_weather_for_city
