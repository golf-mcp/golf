"""Welcome prompt for new users."""


async def welcome() -> list[dict]:
    """Provide a welcome prompt for new users.

    This is a simple example prompt that demonstrates how to define
    a prompt template in GolfMCP.
    """
    return [
        {
            "role": "system",
            "content": (
                "You are an assistant for the {{project_name}} application. "
                "You help users understand how to interact with this system and "
                "its capabilities."
            ),
        },
        {
            "role": "user",
            "content": ("Welcome to {{project_name}}! This is a project built with GolfMCP. How can I get started?"),
        },
    ]


# Designate the entry point function
export = welcome
