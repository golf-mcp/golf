from datetime import datetime, timezone
from sqlalchemy import Column, String, LargeBinary, DateTime, Boolean
from .session import Base

class EncryptionKey(Base):
    __tablename__ = "encryption_keys"

    key_id = Column(String, primary_key=True, index=True)
    key = Column(LargeBinary, nullable=False)  # Encrypted key data
    salt = Column(LargeBinary, nullable=False)  # Salt for the key
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc))
    is_current = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)  # Add is_active column

    def __repr__(self):
        return f"<EncryptionKey(key_id={self.key_id}, created_at={self.created_at}, is_current={self.is_current}, is_active={self.is_active})>" 