from datetime import datetime
from typing import Any, Dict, Optional
from typing_extensions import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    UUID4,
    Field,
    field_validator,
    model_serializer,
)

from ..utils.validation import sanitize_string

NAME_PATTERN = r"^[a-zA-Z0-9_-]{3,50}$"

class ProviderCreate(BaseModel):
    name: Annotated[str, Field(pattern=NAME_PATTERN)]
    contact_email: EmailStr
    registered_user_id: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        return sanitize_string(v, NAME_PATTERN)

    model_config = ConfigDict(
        validate_assignment=True
    )

class Provider(BaseModel):
    id: str
    name: Annotated[str, Field(pattern=NAME_PATTERN)]
    contact_email: EmailStr
    registered_user_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    provider_secret: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        return sanitize_string(v, NAME_PATTERN)

    @model_serializer
    def ser_model(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "contact_email": self.contact_email,
            "registered_user_id": self.registered_user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "provider_secret": self.provider_secret
        }

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True
    )

class ProviderUpdate(BaseModel):
    name: Optional[Annotated[str, Field(pattern=NAME_PATTERN, min_length=3, max_length=50)]] = None
    contact_email: Optional[EmailStr] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            return sanitize_string(v, NAME_PATTERN)
        return v

    model_config = ConfigDict(
        validate_assignment=True
    )