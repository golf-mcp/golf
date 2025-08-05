"""Simple calculator tool for basic arithmetic operations."""

from typing import Annotated

from pydantic import BaseModel, Field


class CalculationResult(BaseModel):
    """Result of a mathematical calculation."""

    result: float
    operation: str
    expression: str


async def calculate(
    expression: Annotated[
        str,
        Field(
            description="Mathematical expression to evaluate (e.g., '2 + 3', '10 * 5', '100 / 4')",
            examples=["2 + 3", "10 * 5.5", "(8 - 3) * 2"],
        ),
    ]
) -> CalculationResult:
    """Evaluate a simple mathematical expression.

    This tool can perform basic arithmetic operations including:
    - Addition (+)
    - Subtraction (-)
    - Multiplication (*)
    - Division (/)
    - Parentheses for grouping
    - Decimal numbers
    
    Examples:
    - calculate("2 + 3") → 5
    - calculate("10 * 5.5") → 55.0
    - calculate("(8 - 3) * 2") → 10
    """
    try:
        # Simple expression evaluation using eval (safe for basic math)
        # In production, consider using a proper math expression parser
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in expression):
            raise ValueError("Expression contains invalid characters")
        
        # Evaluate the expression
        result = eval(expression, {"__builtins__": {}}, {})
        
        # Ensure result is a number
        if not isinstance(result, (int, float)):
            raise ValueError("Expression did not evaluate to a number")
        
        return CalculationResult(
            result=float(result),
            operation="evaluate",
            expression=expression,
        )
        
    except ZeroDivisionError:
        return CalculationResult(
            result=float('inf'),
            operation="error",
            expression=f"{expression} → Division by zero",
        )
    except Exception as e:
        return CalculationResult(
            result=0.0,
            operation="error", 
            expression=f"{expression} → Error: {str(e)}",
        )


# Export the tool
export = calculate
