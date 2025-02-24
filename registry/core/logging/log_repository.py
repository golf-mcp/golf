"""Repository for storing log entries"""
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from pydantic import UUID4
from ...db.session import SessionLocal
from .models import LogLevel, SecurityEvent

class LogRepository:
    def save_event(self, event_type: str, details: Dict[str, Any], is_error: bool = False, level: LogLevel = LogLevel.INFO):
        db = SessionLocal()
        try:
            log_entry = SecurityEvent(
                timestamp=datetime.now(UTC),
                event_type=event_type,
                details=details,
                is_error=is_error,
                level=level
            )
            db.add(log_entry)
            db.commit()
        finally:
            db.close()

    def get_logs(
        self,
        provider_id: Optional[UUID4] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            query = db.query(SecurityEvent)
            
            if provider_id:
                query = query.filter(SecurityEvent.details['provider_id'].astext == provider_id)
            if since:
                query = query.filter(SecurityEvent.timestamp > since)
                
            logs = query.order_by(SecurityEvent.timestamp.desc()).limit(limit).all()
            return [log.to_dict() for log in logs]
        finally:
            db.close() 