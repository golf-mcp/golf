"""Charge payment tool"""

from typing import Annotated
from pydantic import BaseModel, Field
from .common import payment_client


class Output(BaseModel):
    """Response from the charge payment tool."""
    
    success: bool
    charge_id: str
    message: str


async def charge(
    amount: Annotated[float, Field(
        description="Amount to charge in USD",
        gt=0,  # Must be greater than 0
        le=10000  # Maximum charge limit
    )],
    card_token: Annotated[str, Field(
        description="Tokenized payment card identifier",
        pattern=r"^tok_[a-zA-Z0-9]+$"  # Validate token format
    )],
    description: Annotated[str, Field(
        description="Optional payment description for the charge",
        max_length=200
    )] = ""
) -> Output:
    """Process a payment charge.
    
    This example demonstrates nested directory organization where related tools
    are grouped in subdirectories (tools/payments/charge.py).
    
    The resulting tool ID will be: charge-payments
    
    Args:
        amount: Amount to charge in USD
        card_token: Tokenized payment card
        description: Optional payment description
    """
    # The framework will add a context object automatically
    # You can log using regular print during development
    print(f"Processing charge for ${amount:.2f}...")
    
    # Use the shared payment client from common.py
    charge_result = await payment_client.create_charge(
        amount=amount,
        token=card_token,
        description=description
    )
    
    # Create and return the response
    return Output(
        success=True,
        charge_id=charge_result["id"],
        message=f"Successfully charged ${amount:.2f}"
    ) 

export = charge