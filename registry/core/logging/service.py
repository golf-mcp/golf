"""Logging service implementation"""
import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
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
        """Get new logs since the specified time"""
        return await self.repository.get_logs_since(provider_id, since)
        
    def get_logs_for_admin(
        self,
        skip: int = 0,
        limit: int = 100,
        provider_id: Optional[str] = None,
        agent_id: Optional[str] = None, 
        event_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        level: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get logs with pagination and filtering for admin purposes.
        
        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            provider_id: Filter by provider ID
            agent_id: Filter by agent ID
            event_type: Filter by event type 
            from_date: Filter by timestamp (inclusive)
            to_date: Filter by timestamp (inclusive)
            level: Filter by log level
            
        Returns:
            Tuple of (list of log entries, total count)
        """
        try:
            # Build filters list
            filters = []
            
            if provider_id:
                filters.append(("provider_id", provider_id))
                
            if agent_id:
                filters.append(("agent_id", agent_id))
                
            if event_type:
                filters.append(("event_type", event_type))
                
            if level:
                filters.append(("level", level))
                
            if from_date:
                filters.append(("timestamp", ">=", from_date))
                
            if to_date:
                filters.append(("timestamp", "<=", to_date))
                
            # Get logs with filters and pagination
            logs, total_count = self.repository.get_logs_with_filters(
                filters=filters,
                skip=skip,
                limit=limit
            )
            
            # Ensure consistent format for all logs
            formatted_logs = []
            for log in logs:
                formatted_log = {
                    "id": log.get("id"),
                    "timestamp": log.get("timestamp").isoformat() if log.get("timestamp") else None,
                    "level": log.get("level"),
                    "event_type": log.get("event_type"),
                    "details": log.get("details"),
                    "agent_id": log.get("agent_id"),
                    "provider_id": log.get("provider_id"),
                    "resource_type": log.get("resource_type"),
                    "resource_id": log.get("resource_id")
                }
                formatted_logs.append(formatted_log)
                
            return formatted_logs, total_count
            
        except Exception as e:
            self.log_event(
                "get_logs_for_admin_error",
                {
                    "error": str(e),
                    "filters": {
                        "provider_id": provider_id,
                        "agent_id": agent_id,
                        "event_type": event_type,
                        "from_date": from_date,
                        "to_date": to_date,
                        "level": level
                    }
                },
                level=LogLevel.ERROR
            )
            raise 