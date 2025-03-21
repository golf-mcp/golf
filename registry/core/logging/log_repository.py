"""Repository for storing log entries"""
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import UUID4
from sqlalchemy import text
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
                query = query.filter(text("details->>'provider_id' = :provider_id").params(provider_id=str(provider_id)))
            if since:
                query = query.filter(SecurityEvent.timestamp > since)
                
            logs = query.order_by(SecurityEvent.timestamp.desc()).limit(limit).all()
            return [log.to_dict() for log in logs]
        finally:
            db.close()
            
    async def get_logs_since(
        self,
        provider_id: Optional[UUID4] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get logs since the specified timestamp"""
        db = SessionLocal()
        try:
            query = db.query(SecurityEvent)
            
            if provider_id:
                query = query.filter(text("details->>'provider_id' = :provider_id").params(provider_id=str(provider_id)))
            if since:
                query = query.filter(SecurityEvent.timestamp > since)
                
            logs = query.order_by(SecurityEvent.timestamp.desc()).limit(100).all()
            return [log.to_dict() for log in logs]
        finally:
            db.close()
            
    def get_logs_with_filters(
        self,
        filters: List[Union[Tuple[str, Any], Tuple[str, str, Any]]],
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get logs with complex filtering and pagination support.
        
        Args:
            filters: List of filter conditions, each is either:
                   - Tuple of (field_name, value) for exact match
                   - Tuple of (field_name, operator, value) for comparison
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            Tuple of (list of log entries, total count)
        """
        db = SessionLocal()
        try:
            # Start query
            query = db.query(SecurityEvent)
            
            # Apply filters
            for filter_condition in filters:
                if len(filter_condition) == 2:
                    # Simple equality filter
                    field_name, value = filter_condition
                    
                    # Handle JSON fields in details
                    if field_name in ['provider_id', 'agent_id']:
                        # Use text() for JSONB queries
                        query = query.filter(text(f"details->>'{field_name}' = :value").params(value=str(value)))
                    elif field_name == 'event_type':
                        query = query.filter(SecurityEvent.event_type == value)
                    elif field_name == 'level':
                        query = query.filter(SecurityEvent.level == value)
                else:
                    # Comparison filter
                    field_name, operator, value = filter_condition
                    
                    if field_name == 'timestamp':
                        if operator == '>=':
                            query = query.filter(SecurityEvent.timestamp >= value)
                        elif operator == '<=':
                            query = query.filter(SecurityEvent.timestamp <= value)
                        elif operator == '>':
                            query = query.filter(SecurityEvent.timestamp > value)
                        elif operator == '<':
                            query = query.filter(SecurityEvent.timestamp < value)
            
            # Get total count for pagination
            total_count = query.count()
            
            # Apply sorting and pagination
            query = query.order_by(SecurityEvent.timestamp.desc())
            query = query.offset(skip).limit(limit)
            
            # Execute query and convert to dicts
            logs = query.all()
            log_dicts = [log.to_dict() for log in logs]
            
            return log_dicts, total_count
        except Exception as e:
            print(f"Error in get_logs_with_filters: {str(e)}")
            raise
        finally:
            db.close() 