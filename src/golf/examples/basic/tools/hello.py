"""Hello World tool {{project_name}}."""

from typing import Annotated
from pydantic import BaseModel, Field


class Output(BaseModel):
    """Response from the hello tool."""
    
    message: str


async def hello(
    name: Annotated[str, Field(description="The name of the person to greet")] = "World",
    greeting: Annotated[str, Field(description="The greeting phrase to use")] = "Hello"
) -> Output:
    """Say hello to the given name.
    
    This is a simple example tool that demonstrates the basic structure
    of a tool implementation in GolfMCP.
    """
    # The framework will add a context object automatically
    # You can log using regular print during development
    print(f"{greeting} {name}...")
    
    # Create and return the response
    return Output(message=f"{greeting}, {name}!")

# Designate the entry point function
export = hello 