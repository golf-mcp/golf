import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ....db.session import SessionLocal
from .models import SecurityLogDB

class SecurityLogger:
    def __init__(self):
        self.logger = logging.getLogger("security")
        self._setup_logging()

    def _setup_logging(self):
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def log_event(
        self,
        event_type: str,
        details: Dict[str, Any],
        error: bool = False,
        actor_id: Optional[str] = None
    ) -> None:
        """Log a security event to both file and database"""
        timestamp = datetime.now(timezone.utc)
        
        # Log to file
        log_data = {
            "timestamp": timestamp.isoformat(),
            "event_type": event_type,
            "details": details,
            "is_error": error,
            "actor_id": actor_id
        }
        
        if error:
            self.logger.error(json.dumps(log_data))
        else:
            self.logger.info(json.dumps(log_data))

        # Log to database
        try:
            db = SessionLocal()
            log_entry = SecurityLogDB(
                timestamp=timestamp,
                event_type=event_type,
                details=details,
                is_error=error,
                actor_id=actor_id
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            self.logger.error(f"Failed to save log to database: {str(e)}")
        finally:
            db.close()

    def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve logs with filtering"""
        db = SessionLocal()
        try:
            query = db.query(SecurityLogDB)
            
            if start_time:
                query = query.filter(SecurityLogDB.timestamp >= start_time)
            if end_time:
                query = query.filter(SecurityLogDB.timestamp <= end_time)
            if event_type:
                query = query.filter(SecurityLogDB.event_type == event_type)
            if actor_id:
                query = query.filter(SecurityLogDB.actor_id == actor_id)
                
            logs = query.order_by(SecurityLogDB.timestamp.desc()).limit(limit).all()
            return [log.to_dict() for log in logs]
        finally:
            db.close()

# Global instance
security_logger = SecurityLogger() 