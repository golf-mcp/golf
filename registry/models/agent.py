import re
from datetime import datetime
from enum import Enum
from uuid import UUID

from typing import Any, Dict, List, Optional
from typing_extensions import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    UUID4,
    field_validator,
    model_serializer,
)

from ..core.security.encryption import EncryptionManager
from ..utils.validation import sanitize_string, validate_public_key


# Constants
KEY_MIN_LENGTH = 128
KEY_MAX_LENGTH = 2048
NAME_PATTERN = r"^[a-zA-Z0-9_-]{3,50}$"

field_encryption = EncryptionManager()

class PermissionType(str, Enum):
    ALLOW_AGENT = "allow_agent"
    ALLOW_PROVIDER = "allow_provider"

class AgentPermission(BaseModel):
    type: PermissionType
    target_id: str  # Either agent_id or provider_id

    @field_validator('target_id')
    @classmethod
    def validate_target_id(cls, v, info):
        try:
            if info.data['type'] == PermissionType.ALLOW_AGENT:
                UUID(v)
            elif info.data['type'] == PermissionType.ALLOW_PROVIDER:
                if not re.match(r'^[a-zA-Z0-9\s_-]{3,50}$', v):
                    raise ValueError("Invalid provider ID format")
        except ValueError as e:
            raise ValueError(f"Invalid target_id format for type {info.data['type']}: {str(e)}")
        return v

    @model_serializer
    def ser_model(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "target_id": self.target_id
        }

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict) and 'type' in obj:
            # If type is a string value, convert it to enum
            if isinstance(obj['type'], str):
                obj['type'] = PermissionType(obj['type'])
        return super().model_validate(obj, **kwargs)

    model_config = ConfigDict(
        validate_assignment=True,
        from_attributes=True
    )

class AgentRegistration(BaseModel):
    provider_id: UUID4  # Changed from UUID4 to str to match database model
    user_id: Optional[UUID4] = None
    dpop_public_key: str = Field(min_length=KEY_MIN_LENGTH, max_length=KEY_MAX_LENGTH)
    
    @field_validator('dpop_public_key')
    @classmethod
    def validate_keys(cls, v):
        return validate_public_key(v)

    model_config = ConfigDict(validate_assignment=True)

class Agent(BaseModel):
    """Pydantic model for Agent"""
    agent_id: UUID4
    provider_id: UUID4
    user_id: Optional[UUID4] = None
    dpop_public_key: Annotated[str, Field(min_length=KEY_MIN_LENGTH, max_length=KEY_MAX_LENGTH)]
    hashed_secret: str
    name: str = Field(pattern=NAME_PATTERN)
    permissions: List[AgentPermission] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator('dpop_public_key')
    @classmethod
    def validate_keys(cls, v):
        if not v.startswith('20'):
            return validate_public_key(v)
        return v

    def model_post_init(self, __context) -> None:
        if self.dpop_public_key and not self.dpop_public_key.startswith('20'):
            self.dpop_public_key = field_encryption.encrypt_field(self.dpop_public_key)
        if self.hashed_secret and not self.hashed_secret.startswith('20'):
            self.hashed_secret = field_encryption.encrypt_field(self.hashed_secret)

    @model_serializer
    def ser_model(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "provider_id": self.provider_id,
            "user_id": self.user_id,
            "dpop_public_key": self.dpop_public_key,
            "hashed_secret": self.hashed_secret,
            "name": self.name,
            "permissions": self.permissions,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    model_config = ConfigDict(
        from_attributes=True,  # This allows conversion from SQLAlchemy
        validate_assignment=True
    )

class AgentUpdate(BaseModel):
    name: Optional[Annotated[str, Field(pattern=NAME_PATTERN)]]
    permissions: Optional[List[AgentPermission]]
    status: Optional[Annotated[str, Field(pattern='^(active|inactive|suspended)$')]]

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            return sanitize_string(v, NAME_PATTERN)
        return v

    model_config = ConfigDict(validate_assignment=True) 