"""Example resource that provides information about the project."""

import platform
from datetime import datetime
from typing import Any

resource_uri = "info://system"


async def info() -> dict[str, Any]:
    """Provide system information as a resource.

    This is a simple example resource that demonstrates how to expose
    data to an LLM client through the MCP protocol.
    """
    return {
        "project": "{{project_name}}",
        "timestamp": datetime.now().isoformat(),
        "platform": {
            "system": platform.system(),
            "python_version": platform.python_version(),
            "architecture": platform.machine(),
        },
    }


# Designate the entry point function
export = info
