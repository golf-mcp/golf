from typing import Dict

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    JSON,
    String,
    text
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SecurityLogDB(Base):
    __tablename__ = "security_logs"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    event_type = Column(String, nullable=False)
    details = Column(JSON, nullable=False)
    is_error = Column(Boolean, default=False)
    actor_id = Column(String, nullable=True)
    
    def __repr__(self):
        return f"<SecurityLog {self.event_type} at {self.timestamp}>"
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "details": self.details,
            "is_error": self.is_error,
            "actor_id": self.actor_id
        } 