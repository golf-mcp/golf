from enum import Enum as PyEnum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column, 
    DateTime,
    Enum,
    Integer,
    JSON,
    String
)

from ...db.session import Base

class LogLevel(str, PyEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    AUDIT = "audit"

class SecurityEvent(Base):
    __tablename__ = "security_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    event_type = Column(String, nullable=False)
    actor_id = Column(String, nullable=True)
    details = Column(JSON, nullable=False)
    is_error = Column(Boolean, default=False)
    level = Column(Enum(LogLevel), nullable=False, default=LogLevel.INFO)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "details": self.details,
            "is_error": self.is_error,
            "level": self.level.value
        } 