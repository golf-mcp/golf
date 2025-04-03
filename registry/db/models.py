import re
from enum import Enum
from uuid import UUID
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    UUID4,
    field_validator,
    model_serializer,
)
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    String,
    TypeDecorator,
    UUID,
    Boolean
)
from sqlalchemy.orm import relationship

from ..core.config import get_settings
from ..core.security.encryption import EncryptionManager
from ..utils.validation import sanitize_string, validate_public_key
from .session import Base

# Forward references for circular imports
AgentPermission = None
PermissionType = None

# Constants
KEY_MIN_LENGTH = 128
KEY_MAX_LENGTH = 2048
NAME_PATTERN = r"^[a-zA-Z0-9_-]{3,50}$"

settings = get_settings()
field_encryption = EncryptionManager()

# Custom encrypted column type
class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        if value is not None and settings.DB_ENCRYPTION_ENABLED:
            return field_encryption.encrypt_field(value)
        return value

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        if value is not None and settings.DB_ENCRYPTION_ENABLED:
            return field_encryption.decrypt_field(value)
        return value

class EncryptedJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Optional[Dict], dialect) -> Optional[str]:
        if value is not None and settings.DB_ENCRYPTION_ENABLED:
            return field_encryption.encrypt_field(str(value))
        return value

    def process_result_value(self, value: Optional[str], dialect) -> Optional[Dict]:
        if value is not None and settings.DB_ENCRYPTION_ENABLED:
            decrypted = field_encryption.decrypt_field(value)
            return eval(decrypted)  # Safe since we encrypted it ourselves
        return value

class AgentDB(Base):
    __tablename__ = "agents"
    
    agent_id = Column(String, primary_key=True)
    provider_id = Column(String, ForeignKey("providers.id"), nullable=False)
    name = Column(String, nullable=False)
    dpop_public_key = Column(EncryptedString, nullable=False)
    hashed_secret = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    permissions = Column(JSON, default=list)
    provider = relationship("ProviderDB", back_populates="agents")

    @field_validator('dpop_public_key')
    @classmethod
    def validate_keys(cls, v):
        return validate_public_key(v)

    @model_serializer
    def ser_model(self) -> Dict[str, Any]:
        data = {
            "agent_id": self.agent_id,
            "provider_id": self.provider_id,
            "name": self.name,
            "dpop_public_key": self.dpop_public_key,
            "hashed_secret": self.hashed_secret,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "permissions": [
                {
                    "type": p["type"],
                    "target_id": p["target_id"]
                }
                for p in (self.permissions or [])
            ]
        }
        # Encrypt string fields if they have a value
        for field_name, value in data.items():
            if isinstance(value, str) and value:
                data[field_name] = field_encryption.encrypt_field(value)
        return data

    def get_permissions(self) -> List[AgentPermission]:
        """Get permissions as AgentPermission objects."""
        if not self.permissions:
            return []
        return [
            AgentPermission(
                type=PermissionType(p["type"]),
                target_id=p["target_id"]
            )
            for p in self.permissions
        ]

class ProviderDB(Base):
    __tablename__ = "providers"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    registered_user_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    provider_secret = Column(String, nullable=True)
    claimed = Column(Boolean, default=False)
    agents = relationship("AgentDB", back_populates="provider", lazy="dynamic")

    @model_serializer
    def ser_model(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "contact_email": self.contact_email,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "provider_secret": self.provider_secret,
            "claimed": self.claimed
        }

class InteractionTokenDB(Base):
    __tablename__ = "interaction_tokens"

    token_id = Column(UUID, primary_key=True)
    agent_id = Column(UUID, nullable=False)
    token = Column(EncryptedString, nullable=False)  # Encrypted
    scope = Column(EncryptedJSON, nullable=False)  # Encrypted
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)

class RevokedTokenDB(Base):
    __tablename__ = "revoked_tokens"

    token_id = Column(UUID, primary_key=True)
    revoked_at = Column(DateTime, nullable=False)

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
                if not re.match(r'^[A-Za-z0-9-_]{3,50}$', v):
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
        arbitrary_types_allowed=True,
        use_enum_values=True,
        from_attributes=True
    )

# Update forward references
globals()['AgentPermission'] = AgentPermission
globals()['PermissionType'] = PermissionType

class AgentRegistration(BaseModel):
    provider_id: UUID4  # Remove pattern as UUID4 already enforces the format
    user_id: Optional[UUID4] = None  # Remove pattern as UUID4 already enforces the format
    dpop_public_key: str = Field(min_length=KEY_MIN_LENGTH, max_length=KEY_MAX_LENGTH)
    
    @field_validator('dpop_public_key')
    @classmethod
    def validate_keys(cls, v):
        return validate_public_key(v)

class AgentModel(BaseModel):
    agent_id: UUID4
    provider_id: UUID4  # Changed from UUID4 to str to match database
    user_id: Optional[UUID4]
    dpop_public_key: str = Field(min_length=KEY_MIN_LENGTH, max_length=KEY_MAX_LENGTH)
    hashed_secret: str
    name: Optional[str] = Field(pattern=NAME_PATTERN)
    permissions: List[AgentPermission]
    status: str = Field(pattern='^(active|inactive|suspended)$', default="active")
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator('dpop_public_key')
    @classmethod
    def validate_keys(cls, v):
        return validate_public_key(v)

    @model_serializer
    def ser_model(self) -> Dict[str, Any]:
        data = super().model_dump()
        # Encrypt string fields if they have a value
        for field_name, value in data.items():
            if isinstance(value, str) and value:
                data[field_name] = field_encryption.encrypt_field(value)
        return data

    model_config = ConfigDict(validate_assignment=True)

class AgentResponse(BaseModel):  # Response model
    agent_id: UUID4
    provider_id: UUID4
    user_id: Optional[UUID4]
    dpop_public_key: str
    created_at: datetime
    agent_secret: str

class TokenScope(BaseModel):
    allowed_agents: List[str]
    
    @field_validator('allowed_agents')
    @classmethod
    def validate_agent_ids(cls, v):
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
        for agent_id in v:
            if not uuid_pattern.match(agent_id.lower()):
                raise ValueError(f'Invalid agent ID format: {agent_id}')
        return v

class TokenRequest(BaseModel):
    scope: TokenScope
    dpop_proof: str = Field(min_length=50, max_length=2048)  # JWT has reasonable length limits

    @field_validator('dpop_proof')
    @classmethod
    def validate_dpop(cls, v):
        if not re.match(r'^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*$', v):
            raise ValueError('Invalid DPoP proof format')
        return v

class InteractionToken(BaseModel):
    token: str
    scope: TokenScope
    expires_at: datetime
    
    @field_validator('token')
    @classmethod
    def validate_token(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError('Token must be a non-empty string')
        if not re.match(r'^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*$', v):
            raise ValueError('Invalid token format')
        return v

class ProviderUpdate(BaseModel):
    name: Optional[str] = Field(pattern=NAME_PATTERN, min_length=3, max_length=50)
    contact_email: Optional[EmailStr] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            return sanitize_string(v, NAME_PATTERN)
        return v

class AgentUpdate(BaseModel):
    name: Optional[str] = Field(pattern=NAME_PATTERN)
    permissions: Optional[List[AgentPermission]]
    status: Optional[str] = Field(pattern='^(active|inactive|suspended)$')

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            return sanitize_string(v, NAME_PATTERN)
        return v 