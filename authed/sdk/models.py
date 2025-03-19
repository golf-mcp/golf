"""Data models for the Agent Auth SDK."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, UUID4, Field, model_validator, model_serializer, ConfigDict
from uuid import UUID

class PermissionType(str, Enum):
    """Types of agent permissions."""
    ALLOW_AGENT = "allow_agent"
    ALLOW_PROVIDER = "allow_provider"

class AgentPermission(BaseModel):
    """Permission model for agent-to-agent or agent-to-provider permissions."""
    type: PermissionType
    target_id: str

    @model_serializer
    def ser_model(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "target_id": self.target_id
        }

    model_config = ConfigDict(validate_assignment=True)

class Agent(BaseModel):
    """Agent model."""
    agent_id: str
    provider_id: UUID4
    name: Optional[str] = None
    permissions: List[AgentPermission] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    status: str = "active"

class TokenRequest(BaseModel):
    """Model for requesting an interaction token."""
    target_agent_id: UUID4
    dpop_proof: str = Field(..., min_length=50, max_length=2048)

    @model_validator(mode='before')
    @classmethod
    def convert_uuid_to_str(cls, data):
        """Convert UUID to string before validation."""
        if isinstance(data, dict) and 'target_agent_id' in data:
            if isinstance(data['target_agent_id'], UUID):
                data['target_agent_id'] = str(data['target_agent_id'])
        return data

    model_config = {
        'json_encoders': {
            UUID4: str
        }
    }

class InteractionToken(BaseModel):
    """Model for interaction tokens."""
    token: str
    target_agent_id: UUID4
    expires_at: datetime 