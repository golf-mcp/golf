"""Decorators for Golf MCP components."""

from collections.abc import Callable
from typing import TypeVar

F = TypeVar("F", bound=Callable[..., object])


def tool(name: str) -> Callable[[F], F]:
    """Decorator to set an explicit tool name.

    Args:
        name: The tool name to use instead of deriving from file path.

    Example:
        @tool(name="stripe_charge")
        async def run(amount: int) -> str:
            return f"Charged {amount}"
    """

    def decorator(func: F) -> F:
        func._golf_name = name  # type: ignore[attr-defined]
        return func

    return decorator


def resource(name: str) -> Callable[[F], F]:
    """Decorator to set an explicit resource name.

    Args:
        name: The resource name to use instead of deriving from file path.

    Example:
        @resource(name="user_profile")
        async def run(user_id: str) -> dict:
            return {"user_id": user_id}
    """

    def decorator(func: F) -> F:
        func._golf_name = name  # type: ignore[attr-defined]
        return func

    return decorator


def prompt(name: str) -> Callable[[F], F]:
    """Decorator to set an explicit prompt name.

    Args:
        name: The prompt name to use instead of deriving from file path.

    Example:
        @prompt(name="greeting")
        async def run(name: str) -> list:
            return [{"role": "user", "content": f"Hello {name}"}]
    """

    def decorator(func: F) -> F:
        func._golf_name = name  # type: ignore[attr-defined]
        return func

    return decorator
