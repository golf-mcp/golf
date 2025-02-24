from typing import List, Optional
from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel


from ...core.logging.audit import AuditAction, AuditSeverity, audit_logger
from ...models import AgentPermission, AgentRegistration
from ...services import AgentService, PermissionService
from ...core.security.key_manager import KeyManager

router = APIRouter(prefix="/agents", tags=["agents"])
agent_service = AgentService()
permission_service = PermissionService()
key_manager = KeyManager()

@router.post("/register")
async def register_agent(
    registration: AgentRegistration,
):
    try:
        agent_id, agent_secret = agent_service.register_agent(registration)
        
        # Get registry public key
        public_key = key_manager.get_public_key()
        
        # Convert public key to PEM format if it's not already
        if hasattr(public_key, 'public_bytes'):
            # It's an RSA key object
            public_key = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode()
        elif isinstance(public_key, bytes):
            # It's already in bytes, just decode
            public_key = public_key.decode()
        elif not isinstance(public_key, str):
            # Unexpected type
            raise ValueError(f"Unexpected public key type: {type(public_key)}")
        
        audit_logger.log_event(
            event_type=AuditAction.AGENT_CREATE.value,
            details={
                "agent_id": agent_id,
                "provider_id": str(registration.provider_id),
                "user_id": str(registration.user_id) if registration.user_id else None
            }
        )
        
        return {
            "agent_id": agent_id,
            "agent_secret": agent_secret,
            "registry_public_key": public_key
        }
    except ValueError as e:
        error_msg = str(e)
        audit_logger.log_event(
            event_type=AuditAction.AGENT_CREATE.value,
            details={
                "error": error_msg,
                "provider_id": str(registration.provider_id)
            },
            severity=AuditSeverity.ERROR
        )
        if "Provider not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = str(e)
        audit_logger.log_event(
            event_type=AuditAction.AGENT_CREATE.value,
            details={
                "error": error_msg,
                "provider_id": str(registration.provider_id)
            },
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=500, detail=error_msg)    

@router.delete("/delete")
async def delete_agent(
    agent_id: str,
    request: Request
):
    """Delete an agent from the registry
    
    This endpoint requires either:
    1. Internal API key authentication (x-api-key header)
    2. Provider authentication (provider-secret header) - can only delete their own agents
    """
    try:
        # Auth is handled by middleware - if we get here, we're authenticated
        # Check if it's provider auth by looking for provider in request state
        provider = getattr(request.state, 'provider', None)
        auth_method = "provider_auth" if provider else "internal_api"
        provider_id = provider.id if provider else None
        
        # Log the deletion attempt
        audit_logger.log_event(
            event_type=AuditAction.AGENT_DELETE.value,
            details={
                "agent_id": agent_id,
                "provider_id": provider_id,
                "auth_method": auth_method
            }
        )
        
        # Delete the agent
        try:
            deleted = agent_service.delete_agent(agent_id, provider_id)
        except ValueError as e:
            if "not authorized" in str(e):
                raise HTTPException(status_code=403, detail=str(e))
            raise
            
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Agent not found: {agent_id}"
            )
        
        return {"status": "success", "message": f"Agent {agent_id} deleted successfully"}
        
    except ValueError as e:
        error_msg = str(e)
        audit_logger.log_event(
            event_type=AuditAction.AGENT_DELETE.value,
            details={
                "error": error_msg,
                "agent_id": agent_id,
                "provider_id": provider_id if 'provider_id' in locals() else None,
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
            event_type=AuditAction.AGENT_DELETE.value,
            details={
                "error": error_msg,
                "agent_id": agent_id,
                "provider_id": provider_id if 'provider_id' in locals() else None,
                "auth_method": auth_method if 'auth_method' in locals() else "unknown"
            },
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=500, detail=error_msg)


class PermissionOperation(BaseModel):
    add: Optional[List[AgentPermission]] = None
    remove: Optional[List[AgentPermission]] = None

@router.get("/{agent_id}/permissions")
async def get_agent_permissions(
    agent_id: str,
    request: Request
):
    try:
        # Check for internal API key or provider auth
        if not request.headers.get("x-api-key"):
            provider = getattr(request.state, 'provider', None)
            if not provider:
                raise HTTPException(
                    status_code=401,
                    detail="Missing authentication"
                )
            
            # Verify the agent belongs to this provider
            agent = agent_service.get_agent(agent_id)
            if not agent or str(agent.provider_id) != str(provider.id):
                raise HTTPException(
                    status_code=403,
                    detail="Providers can only view permissions for their own agents"
                )
        
        # Get agent permissions
        agent = agent_service.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        audit_logger.log_event(
            event_type=AuditAction.AGENT_PERMISSION_VIEW.value,
            details={
                "agent_id": agent_id,
                "auth_method": "internal_api" if request.headers.get("x-api-key") else "provider_auth"
            }
        )
        
        return {
            "agent_id": agent_id,
            "permissions": [p.model_dump() for p in agent.permissions] if agent.permissions else []
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        error_msg = str(e)
        audit_logger.log_event(
            event_type=AuditAction.AGENT_PERMISSION_VIEW.value,
            details={
                "error": error_msg,
                "agent_id": agent_id
            },
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{agent_id}/permissions")
async def update_agent_permissions(
    agent_id: str,
    permissions: List[AgentPermission],
    request: Request
):
    try:
        # If using agent auth (not internal API key), verify agent can only modify their own permissions
        if not request.headers.get("x-api-key"):
            authenticated_agent_id = request.headers.get("agent-id")
            provider = getattr(request.state, 'provider', None)
            
            # Allow provider to modify their agents' permissions
            if provider:
                # Verify the agent belongs to this provider
                agent = agent_service.get_agent(agent_id)
                if not agent or str(agent.provider_id) != str(provider.id):
                    raise HTTPException(
                        status_code=403,
                        detail="Providers can only modify permissions for their own agents"
                    )
            # Otherwise require agent authentication
            elif authenticated_agent_id:
                if authenticated_agent_id != agent_id:
                    raise HTTPException(
                        status_code=403,
                        detail="Agents can only modify their own permissions"
                    )
            else:
                raise HTTPException(
                    status_code=401,
                    detail="Missing authentication"
                )
        
        # Log the attempt
        audit_logger.log_event(
            event_type=AuditAction.AGENT_PERMISSION_CHANGE.value,
            details={
                "agent_id": agent_id,
                "permissions": [p.model_dump() for p in permissions],
                "auth_method": "internal_api" if request.headers.get("x-api-key") else "provider_auth" if provider else "agent_auth"
            }
        )
        
        # Update permissions
        permission_service.update_agent_permissions(agent_id, permissions)
        
        return {
            "agent_id": agent_id,
            "permissions": [p.model_dump() for p in permissions]
        }
    except ValueError as e:
        error_msg = str(e)
        audit_logger.log_event(
            event_type=AuditAction.AGENT_PERMISSION_CHANGE.value,
            details={
                "error": error_msg,
                "agent_id": agent_id,
                "auth_method": "internal_api" if request.headers.get("x-api-key") else "provider_auth" if provider else "agent_auth"
            },
            severity=AuditSeverity.ERROR
        )
        if "Agent not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = str(e)
        audit_logger.log_event(
            event_type=AuditAction.AGENT_PERMISSION_CHANGE.value,
            details={
                "error": error_msg,
                "agent_id": agent_id,
                "auth_method": "internal_api" if request.headers.get("x-api-key") else "provider_auth" if provider else "agent_auth"
            },
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=500, detail=error_msg)

@router.patch("/{agent_id}/permissions")
async def modify_agent_permissions(
    agent_id: str,
    operations: PermissionOperation,
    request: Request
):
    try:
        # If using agent auth (not internal API key), verify agent can only modify their own permissions
        if not request.headers.get("x-api-key"):
            authenticated_agent_id = request.headers.get("agent-id")
            provider = getattr(request.state, 'provider', None)
            
            # Allow provider to modify their agents' permissions
            if provider:
                # Verify the agent belongs to this provider
                agent = agent_service.get_agent(agent_id)
                if not agent or str(agent.provider_id) != str(provider.id):
                    raise HTTPException(
                        status_code=403,
                        detail="Providers can only modify permissions for their own agents"
                    )
            # Otherwise require agent authentication
            elif authenticated_agent_id:
                if authenticated_agent_id != agent_id:
                    raise HTTPException(
                        status_code=403,
                        detail="Agents can only modify their own permissions"
                    )
            else:
                raise HTTPException(
                    status_code=401,
                    detail="Missing authentication"
                )
        
        audit_logger.log_event(
            event_type=AuditAction.AGENT_PERMISSION_CHANGE.value,
            details={
                "agent_id": agent_id,
                "operations": operations.model_dump(),
                "auth_method": "internal_api" if request.headers.get("x-api-key") else "provider_auth" if provider else "agent_auth"
            }
        )
        
        updated_agent = None
        
        # Process removals first
        if operations.remove:
            for permission in operations.remove:
                try:
                    updated_agent = permission_service.remove_permission(agent_id, permission)
                except ValueError as e:
                    if "Permission not found" not in str(e):
                        raise
        
        # Then process additions
        if operations.add:
            for permission in operations.add:
                updated_agent = permission_service.add_permission(agent_id, permission)
        
        # If no operations were performed, just get current state
        if not updated_agent:
            updated_agent = agent_service.get_agent(agent_id)
            if not updated_agent:
                raise ValueError("Agent not found")
        
        return {
            "agent_id": agent_id,
            "current_permissions": [p.model_dump() for p in updated_agent.permissions] if updated_agent.permissions else []
        }
    except ValueError as e:
        error_msg = str(e)
        audit_logger.log_event(
            event_type=AuditAction.AGENT_PERMISSION_CHANGE.value,
            details={
                "error": error_msg,
                "agent_id": agent_id
            },
            severity=AuditSeverity.ERROR
        )
        if "Agent not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = str(e)
        audit_logger.log_event(
            event_type=AuditAction.AGENT_PERMISSION_CHANGE.value,
            details={
                "error": error_msg,
                "agent_id": agent_id
            },
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=500, detail=error_msg)
