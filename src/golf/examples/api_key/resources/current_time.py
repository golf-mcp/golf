"""Current time resource example."""

from datetime import datetime
from typing import Any

# The URI that clients will use to access this resource
resource_uri = "system://time"


async def current_time() -> dict[str, Any]:
    """Provide the current time in various formats.

    This is a simple resource example that returns time in all formats.
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

    # Return all formats
    return all_formats


# Designate the entry point function
export = current_time
