from typing import Any, Dict, List, Optional
from pydantic import UUID4
from fastapi import APIRouter, HTTPException, Header, Request, Query
from datetime import datetime

from ...core.logging.audit import AuditAction, AuditSeverity, audit_logger
from ...models import Agent, ProviderCreate, ProviderUpdate
from ...services import ProviderService, AgentService
from ...core.config import get_settings

router = APIRouter(prefix="/providers", tags=["providers"])
provider_service = ProviderService()
agent_service = AgentService()

@router.post("/register")
async def register_provider(provider: ProviderCreate):
    """Register a new provider"""
    try:
        return provider_service.register_provider(
            name=provider.name,
            contact_email=provider.contact_email,
            registered_user_id=str(provider.registered_user_id) if provider.registered_user_id else None,
            claimed=provider.registered_user_id is not None  # If registered_user_id is provided, it's from dashboard signup
        )
    except ValueError as e:
        # Handle validation errors with 400 status code
        audit_logger.log_event(
            event_type=AuditAction.PROVIDER_CREATE.value,
            details={
                "error": str(e),
                "name": provider.name
            },
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle other errors with 500 status code
        audit_logger.log_event(
            event_type=AuditAction.PROVIDER_CREATE.value,
            details={
                "error": str(e),
                "name": provider.name
            },
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.patch("/{provider_id}")
async def patch_provider(
    provider_id: UUID4,
    updates: ProviderUpdate,
    request: Request
):
    """Update provider details with partial updates
    
    This endpoint requires either:
    1. Internal API key authentication (x-api-key header)
    2. Provider authentication (provider-secret header) - can only update their own details
    """
    try:
        # Auth is handled by middleware - if we get here, we're authenticated
        # Check if it's provider auth by looking for provider in request state
        provider = getattr(request.state, 'provider', None)
        auth_method = "provider_auth" if provider else "internal_api"
        
        # If using provider auth, verify they're updating their own details
        if provider and str(provider.id) != str(provider_id):
            raise HTTPException(
                status_code=403,
                detail="Providers can only update their own details"
            )
        
        # Log the update attempt
        audit_logger.log_event(
            event_type=AuditAction.PROVIDER_UPDATE.value,
            details={
                "provider_id": provider_id,
                "auth_method": auth_method,
                "updates": updates.model_dump(exclude_unset=True)
            }
        )
        
        # Update the provider
        updated = provider_service.update_provider(provider_id, updates)
        
        return updated
    except ValueError as e:
        audit_logger.log_event(
            event_type=AuditAction.PROVIDER_UPDATE.value,
            details={
                "error": str(e),
                "provider_id": provider_id,
                "updates": updates.model_dump(exclude_unset=True)
            },
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        audit_logger.log_event(
            event_type=AuditAction.PROVIDER_UPDATE.value,
            details={
                "error": str(e),
                "provider_id": provider_id,
                "updates": updates.model_dump(exclude_unset=True)
            },
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{provider_id}/agents", response_model=List[Agent])
async def list_provider_agents(
    provider_id: UUID4,
    provider_secret: str = Header(..., alias="provider-secret")
):
    """Get all agents for a provider"""
    try:
        # First verify the provider secret
        provider = provider_service.get_provider(provider_id)
        
        audit_logger.log_event(
            event_type=AuditAction.PROVIDER_ACCESS.value,
            details={
                "step": "verifying_provider",
                "provider_id": provider_id,
                "provider_exists": provider is not None,
                "secret_matches": provider.provider_secret == provider_secret if provider else None
            }
        )
        
        if not provider or provider.provider_secret != provider_secret:
            raise HTTPException(status_code=401, detail="Invalid provider credentials")
            
        agents = provider_service.get_provider_agents(provider_id)
        
        audit_logger.log_event(
            event_type=AuditAction.PROVIDER_ACCESS.value,
            details={
                "step": "listing_agents",
                "provider_id": provider_id,
                "agent_count": len(agents)
            }
        )
        
        return agents
    except ValueError as e:
        error_msg = str(e)
        audit_logger.log_event(
            event_type=AuditAction.PROVIDER_ACCESS.value,
            details={
                "step": "error",
                "error": error_msg,
                "provider_id": provider_id
            },
            severity=AuditSeverity.WARNING
        )
        if "Provider not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

@router.get("/{provider_id}/stats")
async def get_provider_stats(provider_id: UUID4) -> Dict[str, Any]:
    """Get provider's dashboard stats"""
    try:
        stats = provider_service.get_provider_stats(provider_id)
        
        audit_logger.log_event(
            event_type=AuditAction.PROVIDER_ACCESS.value,
            details={
                "type": "stats",
                "provider_id": provider_id
            }
        )
        
        return stats
    except ValueError as e:
        audit_logger.log_event(
            event_type=AuditAction.PROVIDER_ACCESS.value,
            details={
                "error": str(e),
                "provider_id": provider_id
            },
            severity=AuditSeverity.WARNING
        )
        raise HTTPException(status_code=404, detail=str(e)) 
    



@router.get("/list-agents/{provider_id}")
async def list_provider_agents(
    provider_id: str,
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    include_inactive: bool = Query(default=False)
):
    """List all agents for a specific provider
    
    This endpoint requires either:
    1. Internal API key authentication (x-api-key header)
    2. Provider authentication (provider-secret header) - can only list their own agents
    
    Args:
        provider_id: The ID of the provider whose agents to list
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        include_inactive: Whether to include inactive agents
    """
    try:
        # Auth is handled by middleware - if we get here, we're authenticated
        # Check if it's provider auth by looking for provider in request state
        provider = getattr(request.state, 'provider', None)
        auth_method = "provider_auth" if provider else "internal_api"
        
        # If using provider auth, verify they're requesting their own agents
        if provider and str(provider.id) != str(provider_id):
            raise HTTPException(
                status_code=403,
                detail="Providers can only list their own agents"
            )
        
        # Log the list attempt
        audit_logger.log_event(
            event_type=AuditAction.AGENT_LIST.value,
            details={
                "provider_id": provider_id,
                "auth_method": auth_method,
                "include_inactive": include_inactive,
                "skip": skip,
                "limit": limit
            }
        )
        
        # Get the agents
        try:
            agents = agent_service.get_provider_agents(
                provider_id=provider_id,
                skip=skip,
                limit=limit,
                include_inactive=include_inactive
            )
            
            return {
                "total": len(agents),
                "skip": skip,
                "limit": limit,
                "agents": [agent.model_dump() for agent in agents]
            }
            
        except ValueError as e:
            if "Provider not found" in str(e):
                raise HTTPException(status_code=404, detail=str(e))
            raise
            
    except ValueError as e:
        error_msg = str(e)
        audit_logger.log_event(
            event_type=AuditAction.AGENT_LIST.value,
            details={
                "error": error_msg,
                "provider_id": provider_id,
                "auth_method": auth_method if 'auth_method' in locals() else "unknown"
            },
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        error_msg = str(e)
        audit_logger.log_event(
            event_type=AuditAction.AGENT_LIST.value,
            details={
                "error": error_msg,
                "provider_id": provider_id,
                "auth_method": auth_method if 'auth_method' in locals() else "unknown"
            },
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/admin/list")
async def admin_list_providers(
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    name: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    include_inactive: bool = Query(default=False)
):
    """
    Admin endpoint to list all providers with pagination and filtering options.
    Protected by internal API key.
    """
    # Check for internal API key auth
    api_key = request.headers.get("x-api-key")
    if not api_key or api_key != get_settings().INTERNAL_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    
    # Get providers with filters
    providers, total_count = provider_service.list_providers(
        skip=skip,
        limit=limit,
        name=name,
        from_date=from_date,
        to_date=to_date,
        include_inactive=include_inactive
    )
    
    # Log access for audit trail
    audit_logger.log_event(
        event_type=AuditAction.ADMIN_QUERY.value,
        details={
            "endpoint": "admin_list_providers",
            "filters": {
                "skip": skip,
                "limit": limit,
                "name": name,
                "from_date": from_date.isoformat() if from_date else None,
                "to_date": to_date.isoformat() if to_date else None,
                "include_inactive": include_inactive
            }
        },
        severity=AuditSeverity.INFO
    )
    
    return {
        "providers": providers,  # Now contains dictionaries with stats
        "pagination": {
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + limit) < total_count
        }
    }