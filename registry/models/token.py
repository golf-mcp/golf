import re
from datetime import datetime


from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    UUID4,
)

class TokenRequest(BaseModel):
    """Request for a new interaction token."""
    target_agent_id: UUID4
    dpop_proof: str = Field(..., min_length=50, max_length=2048)

    @field_validator('dpop_proof')
    @classmethod
    def validate_dpop(cls, v):
        if not re.match(r'^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*$', v):
            raise ValueError('Invalid DPoP proof format')
        return v

    model_config = ConfigDict(validate_assignment=True)

class InteractionToken(BaseModel):
    """Model for interaction tokens."""
    token: str
    target_agent_id: UUID4
    expires_at: datetime
    
    @field_validator('token')
    @classmethod
    def validate_token(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError('Token must be a non-empty string')
        if not re.match(r'^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*$', v):
            raise ValueError('Invalid token format')
        return v

    model_config = ConfigDict(validate_assignment=True) 