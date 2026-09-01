"""Welcome prompt for new users."""

from mcp_types import PromptMessage, TextContent


async def welcome() -> list[PromptMessage]:
    """Provide a welcome prompt for new users.

    This is a simple example prompt that demonstrates how to define
    a prompt template in GolfMCP.
    """
    return [
        PromptMessage(
            role="assistant",
            content=TextContent(
                type="text",
                text=(
                    "You are an assistant for the {{project_name}} application. "
                    "You help users understand how to interact with this system and "
                    "its capabilities."
                ),
            ),
        ),
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text="Welcome to {{project_name}}! This is a project built with GolfMCP. How can I get started?",
            ),
        ),
    ]


# Designate the entry point function
export = welcome
