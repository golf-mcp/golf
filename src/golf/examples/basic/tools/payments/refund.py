"""Refund payment tool"""

from typing import Annotated, Optional
from pydantic import BaseModel, Field
from .common import payment_client


class Output(BaseModel):
    """Response from the refund payment tool."""
    
    success: bool
    refund_id: str
    message: str


async def refund(
    charge_id: Annotated[str, Field(
        description="The ID of the charge to refund",
        pattern=r"^ch_[a-zA-Z0-9]+$"
    )],
    amount: Annotated[Optional[float], Field(
        description="Amount to refund in USD. If not specified, refunds the full charge amount",
        gt=0,
        default=None
    )] = None,
    reason: Annotated[str, Field(
        description="Reason for the refund",
        min_length=3,
        max_length=200
    )] = "Customer request"
) -> Output:
    """Process a payment refund.
    
    This example demonstrates nested directory organization where related tools
    are grouped in subdirectories (tools/payments/refund.py).
    
    The resulting tool ID will be: refund-payments
    """
    # The framework will add a context object automatically
    # You can log using regular print during development
    print(f"Processing refund for charge {charge_id}...")
    
    # Use the shared payment client from common.py
    refund_result = await payment_client.create_refund(
        charge_id=charge_id,
        amount=amount,
        reason=reason
    )
    
    # Create and return the response
    return Output(
        success=True,
        refund_id=refund_result["id"],
        message=f"Successfully refunded charge {charge_id}"
    )

export = refund