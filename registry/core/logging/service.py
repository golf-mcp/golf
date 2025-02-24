"""Logging service implementation"""
import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import UUID4
from ..config import get_settings
from .log_repository import LogRepository
from .models import LogLevel

def redact_sensitive_data(data: Any) -> Any:
    """Redact sensitive information from logs"""
    if isinstance(data, str):
        # Redact PEM keys
        data = re.sub(
            r'-----BEGIN .*?KEY-----.*?-----END .*?KEY-----',
            '[REDACTED KEY]',
            data,
            flags=re.DOTALL
        )
        return data
    elif isinstance(data, dict):
        return {k: redact_sensitive_data(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [redact_sensitive_data(x) for x in data]
    return data

class JSONFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                **record.msg
            }
            # Include extra attributes if they exist
            if hasattr(record, 'extra'):
                log_entry.update(record.extra)
            return json.dumps(log_entry)
            
        log_entry = {
            "message": record.msg,
            "level": record.levelname,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        # Include extra attributes if they exist
        if hasattr(record, 'extra'):
            log_entry.update(record.extra)
        return json.dumps(log_entry)

class LogService:
    def __init__(self, repository: LogRepository):
        self.settings = get_settings()
        self.logger = logging.getLogger("registry")
        self.repository = repository
        self._setup_logging()
        
    def _setup_logging(self):
        """Configure structured logging"""
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)
        self.logger.setLevel(self.settings.LOG_LEVEL)

    def log_event(
        self,
        event_type: str,
        details: Dict[str, Any],
        level: LogLevel = LogLevel.INFO,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None
    ):
        """Log an event with full context"""
        enriched_details = {
            **details,
            "actor_id": actor_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "environment": self.settings.ENV,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Log to file
        level_value = level.value if isinstance(level, LogLevel) else level.lower()
        log_method = getattr(self.logger, level_value)
        log_data = {
            "event_type": event_type,
            "message": event_type,
            **redact_sensitive_data(enriched_details)
        }
        log_method(log_data)  # Pass the entire log_data as the message

        # Save to database
        self.repository.save_event(
            event_type=event_type,
            details=redact_sensitive_data(enriched_details),
            is_error=level in [LogLevel.ERROR, LogLevel.WARNING] if isinstance(level, LogLevel) else level.upper() in ["ERROR", "WARNING"],
            level=level
        )

    def audit_log(
        self,
        action: str,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        changes: Dict[str, Any],
        status: str = "success"
    ):
        """Specific method for audit logging"""
        self.log_event(
            event_type=f"audit.{action}",
            details={
                "changes": changes,
                "status": status
            },
            level=LogLevel.AUDIT,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id
        )

    async def get_new_logs(
        self,
        provider_id: Optional[UUID4] = None,
        since: Optional[datetime] = None
    ) -> List[Dict]:
        """Get new logs since last check"""
        return self.repository.get_logs(provider_id=provider_id, since=since) 