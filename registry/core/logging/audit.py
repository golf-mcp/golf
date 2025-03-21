import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...db.session import SessionLocal
from ..config import get_settings
from .models import LogLevel, SecurityEvent

class AuditCategory(str, Enum):
    SECURITY = "security"
    ACCESS = "access"
    DATA = "data"
    SYSTEM = "system"

class AuditSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AuditAction(str, Enum):
    # Provider actions
    PROVIDER_CREATE = "provider_create"
    PROVIDER_UPDATE = "provider_update"
    PROVIDER_DELETE = "provider_delete"
    PROVIDER_STATUS_CHANGE = "provider_status_change"
    PROVIDER_ACCESS = "provider_access"
    
    # Agent actions
    AGENT_CREATE = "agent_create"
    AGENT_UPDATE = "agent_update"
    AGENT_DELETE = "agent_delete"
    AGENT_LIST = "agent_list"
    AGENT_STATUS_CHANGE = "agent_status_change"
    AGENT_PERMISSION_CHANGE = "agent_permission_change"
    AGENT_PERMISSION_VIEW = "agent_permission_view"
    
    # Admin actions 
    ADMIN_QUERY = "admin_query"
    ADMIN_ACTION = "admin_action"
    
    # Security events
    KEY_ROTATION = "key_rotation"
    ENCRYPTION_FAILURE = "encryption_failure"
    AUTHENTICATION_FAILURE = "authentication_failure"
    TOKEN_REVOCATION = "token_revocation"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    
    # Token events
    TOKEN_ISSUED = "token_issued"
    TOKEN_ISSUE_FAILED = "token_issue_failed"
    TOKEN_VERIFIED = "token_verified"
    TOKEN_VERIFICATION_FAILED = "token_verification_failed"
    
    # Data operations
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    BACKUP_CREATE = "backup_create"
    BACKUP_RESTORE = "backup_restore"
    
    # System events
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    MAINTENANCE_MODE = "maintenance_mode"

class AuditLogger:
    def __init__(self):
        self.settings = get_settings()

    def log_event(
        self,
        event_type: str,
        details: Dict[str, Any],
        severity: AuditSeverity = AuditSeverity.INFO,
        category: AuditCategory = AuditCategory.SYSTEM,
        actor_id: Optional[str] = None
    ) -> None:
        """Log an event"""
        self._log_event(
            event_type=event_type,
            actor_id=actor_id,
            category=category,
            severity=severity,
            details=details
        )

    def log_security_event(
        self,
        action: AuditAction,
        details: Dict[str, Any],
        severity: AuditSeverity = AuditSeverity.WARNING,
        actor_id: Optional[str] = None,
        level: LogLevel = LogLevel.INFO
    ) -> None:
        """Log a security-related event"""
        self._log_event(
            event_type=action,
            actor_id=actor_id,
            category=AuditCategory.SECURITY,
            severity=severity,
            details=details
        )

    def log_data_access(
        self,
        action: AuditAction,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        access_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log data access events"""
        self._log_event(
            event_type=action,
            actor_id=actor_id,
            category=AuditCategory.ACCESS,
            severity=AuditSeverity.INFO,
            details={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "access_type": access_type,
                **(details or {})
            }
        )

    def _log_event(
        self,
        event_type: AuditAction,
        category: AuditCategory,
        severity: AuditSeverity,
        actor_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Internal method to log events to the database"""
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        event_details = {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "category": category,
            "severity": severity,
            "actor_id": actor_id,
            **(details or {})
        }
        
        db = SessionLocal()
        try:
            log_entry = SecurityEvent(
                timestamp=timestamp,
                event_type=event_type,
                details=event_details,
                is_error=severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]
            )
            db.add(log_entry)
            db.commit()
            
        finally:
            db.close()

    def get_audit_trail(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        category: Optional[AuditCategory] = None,
        severity: Optional[AuditSeverity] = None,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve audit trail with flexible filtering"""
        db = SessionLocal()
        try:
            query = db.query(SecurityEvent)
            
            if start_time:
                query = query.filter(SecurityEvent.timestamp >= start_time)
            if end_time:
                query = query.filter(SecurityEvent.timestamp <= end_time)
            if category:
                query = query.filter(SecurityEvent.details['category'].astext == category)
            if severity:
                query = query.filter(SecurityEvent.details['severity'].astext == severity)
            if actor_id:
                query = query.filter(SecurityEvent.details['actor_id'].astext == actor_id)
            if resource_type:
                query = query.filter(SecurityEvent.details['resource_type'].astext == resource_type)
            if resource_id:
                query = query.filter(SecurityEvent.details['resource_id'].astext == resource_id)
                
            logs = query.order_by(SecurityEvent.timestamp.desc()).limit(limit).all()
            
            return [
                {
                    "event_type": log.event_type,
                    "timestamp": log.timestamp.isoformat(),
                    "is_error": log.is_error,
                    **log.details
                }
                for log in logs
            ]
            
        finally:
            db.close()

# Global instance
audit_logger = AuditLogger() 