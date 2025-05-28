"""Payments shared functionality.

This common.py file demonstrates the recommended pattern for
sharing functionality across multiple tools in a directory.
"""

import os

# Read configuration from environment variables
PAYMENT_API_KEY = os.environ.get("PAYMENT_API_KEY", "mock_key")
PAYMENT_API_URL = os.environ.get("PAYMENT_API_URL", "https://api.example.com/payments")


class PaymentClient:
    """Mock payment provider client."""

    def __init__(
        self, api_key: str = PAYMENT_API_KEY, api_url: str = PAYMENT_API_URL
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url

    async def create_charge(self, amount: float, token: str, **kwargs):
        """Create a charge (mock implementation)."""
        # In a real implementation, this would make an API request
        # using the configured API key and URL
        return {"id": f"ch_{int(amount * 100)}_{hash(token) % 10000:04d}"}

    async def create_refund(self, charge_id: str, amount: float, **kwargs):
        """Create a refund (mock implementation)."""
        # In a real implementation, this would make an API request
        return {"id": f"ref_{charge_id}_{int(amount * 100)}"}


# Create a shared payment client that can be imported by all tools in this directory
payment_client = PaymentClient()
