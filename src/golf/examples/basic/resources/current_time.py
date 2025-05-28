"""Current time resource example."""

from datetime import datetime
from typing import Any

# The URI that clients will use to access this resource
resource_uri = "system://time/{format}"


async def current_time(format: str = "full") -> dict[str, Any]:
    """Provide the current time in various formats.

    This is a simple resource example that accepts a format parameter.

    Args:
        format: The format to return ('full', 'iso', 'unix' or 'rfc')
    """
    now = datetime.now()

    # Prepare all possible formats
    all_formats = {
        "iso": now.isoformat(),
        "rfc": now.strftime("%a, %d %b %Y %H:%M:%S %z"),
        "unix": int(now.timestamp()),
        "formatted": {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "timezone": now.astimezone().tzname(),
        },
    }

    # Return specific format or all formats
    if format == "full":
        return all_formats
    elif format in all_formats:
        return {format: all_formats[format]}
    else:
        return {"error": f"Unknown format: {format}"}


# Designate the entry point function
export = current_time
