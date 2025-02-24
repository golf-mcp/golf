"""Token management endpoints."""

from fastapi import APIRouter, Header, HTTPException, Request
from typing import Optional
from uuid import UUID

from ...core.logging.audit import AuditAction, audit_logger
from ...models import TokenRequest, InteractionToken
from ...services import TokenService, AgentService

router = APIRouter(prefix="/tokens", tags=["tokens"])
token_service = TokenService()
agent_service = AgentService()

def ensure_https_url(url: str) -> str:
    """Ensure URL uses HTTPS scheme."""
    if url.startswith("http://"):
        return "https://" + url[7:]
    return url

@router.post("/create")
async def create_token(
    request: Request,
    token_request: TokenRequest,
    agent_id: str = Header(..., alias="agent-id"),
    dpop_public_key: str = Header(..., alias="dpop-public-key")
) -> InteractionToken:
    """Create a new interaction token.
    
    The token will be bound to:
    1. The requesting agent (from agent-id header)
    2. The target agent (from request body)
    3. The DPoP proof (from request body)
    
    Both agents must have permissions for each other (either directly or via provider permissions).
    """
    try:
        # Log the token creation attempt
        audit_logger.log_event(
            event_type=AuditAction.TOKEN_ISSUED,
            details={
                "agent_id": agent_id,
                "target_agent_id": str(token_request.target_agent_id)
            }
        )
        
        # Create the token with HTTPS URL
        token = token_service.create_interaction_token(
            agent_id=UUID(agent_id),
            target_agent_id=token_request.target_agent_id,
            dpop_proof=token_request.dpop_proof,
            dpop_public_key=dpop_public_key,
            method=request.method,
            url=ensure_https_url(str(request.url))
        )
        
        return token
        
    except ValueError as e:
        # This covers permission errors, invalid DPoP proofs, etc.
        audit_logger.log_event(
            event_type=AuditAction.TOKEN_ISSUE_FAILED,
            details={
                "error": str(e),
                "agent_id": agent_id,
                "target_agent_id": str(token_request.target_agent_id)
            }
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        audit_logger.log_event(
            event_type=AuditAction.TOKEN_ISSUE_FAILED,
            details={
                "error": str(e),
                "agent_id": agent_id,
                "target_agent_id": str(token_request.target_agent_id)
            }
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/verify")
async def verify_token(
    request: Request,
    token: str = Header(..., alias="authorization"),
    dpop: Optional[str] = Header(None),
    expected_target: Optional[UUID] = Header(None, alias="target-agent-id")
) -> dict:
    """Verify an interaction token.
    
    Verifies:
    1. Token signature and expiry
    2. DPoP proof from verifying agent
    3. Target agent matches (if expected_target provided)
    4. Permissions are still valid between agents
    """
    try:
        # Strip 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token.replace("Bearer ", "")
            
        # Log the verification attempt
        audit_logger.log_event(
            event_type=AuditAction.TOKEN_VERIFIED,
            details={
                "expected_target": str(expected_target) if expected_target else None
            }
        )
        
        # Verify the token with HTTPS URL
        payload = token_service.verify_token(
            token=token,
            expected_target=expected_target,
            dpop_proof=dpop,
            method=request.method,
            url=ensure_https_url(str(request.url))
        )
        
        return {
            "valid": True,
            "subject": payload["sub"],
            "target": payload["target"],
            "expires_at": payload["exp"]
        }
        
    except ValueError as e:
        audit_logger.log_event(
            event_type=AuditAction.TOKEN_VERIFICATION_FAILED,
            details={
                "error": str(e),
                "expected_target": str(expected_target) if expected_target else None
            }
        )
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        audit_logger.log_event(
            event_type=AuditAction.TOKEN_VERIFICATION_FAILED,
            details={
                "error": str(e),
                "expected_target": str(expected_target) if expected_target else None
            }
        )
        raise HTTPException(status_code=500, detail="Internal server error") 