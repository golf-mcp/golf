import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Generator
from pydantic import UUID4

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, Request
from sqlalchemy.orm import Session

from ...db import SessionLocal
from ...core.logging.logging import log_service
from ...core.logging.models import SecurityEvent
from ...services import AgentService, ProviderService
from ...core.config import get_settings

router = APIRouter(prefix="/logs", tags=["logs"])
agent_service = AgentService()
provider_service = ProviderService()

def get_db() -> Generator:
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_log_access(
    request: Request,
    provider_id: Optional[UUID4] = None,
    agent_id: Optional[UUID4] = None
) -> bool:
    """Verify if the requester has access to the requested logs
    
    Rules:
    1. Internal API key (x-api-key) has access to all logs
    2. Provider (provider-secret) can access their own logs and their agents' logs
    3. Agent (agent-id) can only access their own logs
    """
    # Check for internal API key
    if request.headers.get("x-api-key") == get_settings().INTERNAL_API_KEY:
        print("Access granted via internal API key")  # Debug log
        return True
        
    # Check for provider auth
    provider = getattr(request.state, 'provider', None)
    print(f"Provider from state: {provider.id if provider else None}")  # Debug log
    
    if provider:
        # If no filters are provided, allow access to all provider's logs
        if not provider_id and not agent_id:
            print("Access granted to provider (no filters)")  # Debug log
            return True
            
        # Provider can access their own logs
        if provider_id and str(provider.id) == str(provider_id):
            print("Access granted to provider (own logs)")  # Debug log
            return True
            
        # Provider can access their agents' logs
        if agent_id:
            try:
                agent = agent_service.get_agent(str(agent_id))
                print(f"Agent found: {agent.agent_id if agent else None}")  # Debug log
                print(f"Agent provider_id: {agent.provider_id if agent else None}")  # Debug log
                if agent and str(agent.provider_id) == str(provider.id):
                    print("Access granted to provider (agent logs)")  # Debug log
                    return True
            except ValueError as e:
                print(f"Error getting agent: {str(e)}")  # Debug log
                return False
        print("Provider access denied")  # Debug log
        return False
        
    # Check for agent auth
    agent_auth_id = request.headers.get("agent-id")
    if agent_auth_id:
        # Agent can only access their own logs
        has_access = agent_id and str(agent_id) == agent_auth_id
        print(f"Agent auth check: {has_access}")  # Debug log
        return has_access
        
    # No valid auth found
    print("No valid authentication found")  # Debug log
    return False

@router.get("")
async def get_logs(
    request: Request,
    provider_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    event_type: Optional[str] = None,
    from_date: Optional[datetime] = None,
    level: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get filtered logs for frontend display
    
    Authentication:
    - Internal API key (x-api-key header) can access all logs
    - Provider (provider-secret header) can access their own logs and their agents' logs
    - Agent (agent-id header) can only access their own logs
    """
    try:
        # Convert string IDs to UUID if provided
        provider_uuid = UUID4(provider_id) if provider_id else None
        agent_uuid = UUID4(agent_id) if agent_id else None
        
        # Verify access
        if not verify_log_access(request, provider_uuid, agent_uuid):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to access these logs"
            )
        
        query = db.query(SecurityEvent)
        
        # Apply filters
        if provider_id:
            query = query.filter(SecurityEvent.details.op('->>')('provider_id') == provider_id)
        if agent_id:
            query = query.filter(SecurityEvent.details.op('->>')('agent_id') == agent_id)
        if event_type:
            query = query.filter(SecurityEvent.event_type == event_type)
        if from_date:
            query = query.filter(SecurityEvent.timestamp >= from_date)
        if level:
            query = query.filter(SecurityEvent.level == level)
            
        # If using provider auth without filters, only show logs for that provider
        provider = getattr(request.state, 'provider', None)
        if provider and not provider_id and not agent_id:
            query = query.filter(SecurityEvent.details.op('->>')('provider_id') == str(provider.id))
            
        # Order by timestamp desc and limit results
        logs = query.order_by(SecurityEvent.timestamp.desc()).limit(limit).all()
        
        return [
            {
                "timestamp": log.timestamp,
                "event_type": log.event_type,
                "details": log.details,
                "level": log.level,
                "is_error": log.is_error
            }
            for log in logs
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {str(e)}")
    finally:
        db.close()

@router.websocket("/ws")
async def websocket_logs(
    websocket: WebSocket,
    provider_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    level: Optional[str] = None,
    event_type: Optional[str] = None
):
    """Stream logs in real-time to frontend
    
    Authentication:
    - Internal API key (x-api-key header) can access all logs
    - Provider (provider-secret header) can access their own logs and their agents' logs
    - Agent (agent-id header) can only access their own logs
    """
    # Create a single database session for the connection
    db = SessionLocal()
    try:
        # Convert string IDs to UUID if provided
        provider_uuid = UUID4(provider_id) if provider_id else None
        agent_uuid = UUID4(agent_id) if agent_id else None
        
        # Get headers from websocket
        headers = dict(websocket.headers)
        print(f"WebSocket headers: {headers}")  # Debug log

        # Check authentication
        authenticated_provider = None
        is_internal = False

        # Check for internal API key first
        if headers.get("x-api-key") == get_settings().INTERNAL_API_KEY:
            print("Using internal API key auth")  # Debug log
            is_internal = True
        # Check provider authentication
        elif provider_secret := headers.get("provider-secret"):
            print(f"Checking provider secret: {provider_secret[:10]}...")  # Debug log
            try:
                provider = provider_service.get_provider_by_secret(provider_secret)
                if provider:
                    print(f"Found provider: {provider.id}")  # Debug log
                    authenticated_provider = provider
                else:
                    print("Provider not found for secret")  # Debug log
                    await websocket.close(code=4003)  # Custom close code for unauthorized
                    return
            except Exception as e:
                print(f"Error getting provider: {str(e)}")  # Debug log
                await websocket.close(code=4500, reason=str(e))
                return
        else:
            print("No authentication provided")  # Debug log
            await websocket.close(code=4003)  # Custom close code for unauthorized
            return

        # Verify access
        has_access = False
        if is_internal:
            has_access = True
        elif authenticated_provider:
            # If no filters are provided, allow access to all provider's logs
            if not provider_id and not agent_id:
                has_access = True
            # Provider can access their own logs
            elif provider_id and str(authenticated_provider.id) == str(provider_id):
                has_access = True
            # Provider can access their agents' logs
            elif agent_id:
                try:
                    agent = agent_service.get_agent(str(agent_id))
                    print(f"Agent found: {agent.agent_id if agent else None}")  # Debug log
                    print(f"Agent provider_id: {agent.provider_id if agent else None}")  # Debug log
                    if agent and str(agent.provider_id) == str(authenticated_provider.id):
                        has_access = True
                except ValueError as e:
                    print(f"Error getting agent: {str(e)}")  # Debug log
        # Check for agent auth
        elif agent_auth_id := headers.get("agent-id"):
            has_access = agent_id and str(agent_id) == agent_auth_id

        if not has_access:
            print(f"Access denied. Provider ID: {provider_uuid}, Agent ID: {agent_uuid}")  # Debug log
            await websocket.close(code=4003)  # Custom close code for unauthorized
            return

        await websocket.accept()
        print("WebSocket connection accepted")  # Debug log
        
        # Keep track of last check time and last seen ID
        last_check = datetime.now()
        last_id = 0  # Track the last seen log ID
        
        while True:
            try:
                # Build efficient query using ID-based pagination and timestamp
                query = db.query(SecurityEvent).filter(
                    SecurityEvent.id > last_id,
                    SecurityEvent.timestamp > last_check
                )
                
                # Apply filters
                if provider_id:
                    query = query.filter(SecurityEvent.details.op('->>')('provider_id') == str(provider_id))
                if agent_id:
                    query = query.filter(SecurityEvent.details.op('->>')('agent_id') == str(agent_id))
                if level:
                    query = query.filter(SecurityEvent.level == level)
                if event_type:
                    query = query.filter(SecurityEvent.event_type == event_type)
                    
                # Use efficient ordering and limit
                query = query.order_by(SecurityEvent.id.asc()).limit(100)
                logs = query.all()
                
                if logs:
                    # Update last seen ID
                    last_id = max(log.id for log in logs)
                    
                    filtered_logs = [{
                        'timestamp': log.timestamp.isoformat(),
                        'event_type': log.event_type,
                        'details': log.details,
                        'level': log.level,
                        'is_error': log.is_error
                    } for log in logs]
                    
                    await websocket.send_json(filtered_logs)
                
                # Commit and expire to refresh session
                db.commit()
                db.expire_all()
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Error in log processing loop: {str(e)}")  # Debug log
                db.rollback()  # Rollback on error
                continue
            
    except WebSocketDisconnect:
        print("WebSocket disconnected")  # Debug log
    except ValueError as e:
        print(f"ValueError: {str(e)}")  # Debug log
        await websocket.close(code=4000, reason=f"Invalid UUID format: {str(e)}")
    except Exception as e:
        import traceback
        print(f"Unexpected error: {str(e)}")  # Debug log
        print(f"Error traceback: {traceback.format_exc()}")  # Debug log full traceback
        await websocket.close(code=4500, reason=str(e))
    finally:
        db.close() 