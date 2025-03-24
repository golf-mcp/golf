from datetime import datetime, timezone
from typing import List

from ..core.security.encryption import EncryptionManager
from ..db.models import AgentDB, ProviderDB
from ..db.session import SessionLocal
from ..models import Agent, AgentPermission, PermissionType
from ..core.logging.models import LogLevel
from ..core.logging.logging import log_service

encryption_manager = EncryptionManager()

class PermissionService:
    def add_permission(
        self,
        agent_id: str,
        permission: AgentPermission
    ) -> Agent:
        """Add a permission for an agent"""
        db = SessionLocal()
        try:
            agent = db.query(AgentDB).filter(AgentDB.agent_id == agent_id).first()
            if not agent:
                raise ValueError("Agent not found")
            
            # Initialize permissions if None
            if agent.permissions is None:
                agent.permissions = []
            
            # Validate the permission
            if permission.type == PermissionType.ALLOW_AGENT:
                # Check if target agent exists
                target_agent = db.query(AgentDB).filter(
                    AgentDB.agent_id == permission.target_id
                ).first()
                if not target_agent:
                    raise ValueError(f"Target agent not found: {permission.target_id}")
            elif permission.type == PermissionType.ALLOW_PROVIDER:
                # Check if target provider exists
                target_provider = db.query(ProviderDB).filter(
                    ProviderDB.id == permission.target_id
                ).first()
                if not target_provider:
                    raise ValueError(f"Target provider not found: {permission.target_id}")
            
            # Check if permission already exists
            for existing_perm in agent.permissions or []:
                if (existing_perm.get("type") == permission.type.value and 
                    existing_perm.get("target_id") == permission.target_id):
                    # Permission already exists
                    return Agent.model_validate(agent)
            
            # Convert permission to dictionary with proper enum value
            permission_dict = {
                "type": permission.type.value,
                "target_id": permission.target_id
            }
            
            # Add the new permission
            if not agent.permissions:
                agent.permissions = []
            agent.permissions.append(permission_dict)
            agent.updated_at = datetime.now(timezone.utc)
            db.commit()
            
            # Decrypt sensitive fields before converting to Agent model
            if agent.dpop_public_key:
                agent.dpop_public_key = encryption_manager.decrypt_field(agent.dpop_public_key)
            return Agent.model_validate(agent)
        finally:
            db.close()

    def update_agent_permissions(
        self,
        agent_id: str,
        permissions: List[AgentPermission]
    ) -> Agent:
        """Update an agent's permissions"""
        db = SessionLocal()
        try:
            agent = db.query(AgentDB).filter(
                AgentDB.agent_id == agent_id
            ).first()
            
            if not agent:
                raise ValueError("Agent not found")
            
            # Initialize permissions if None
            if agent.permissions is None:
                agent.permissions = []
            
            # Validate each permission
            for permission in permissions:
                if permission.type == PermissionType.ALLOW_AGENT:
                    # Check if target agent exists
                    target_agent = db.query(AgentDB).filter(
                        AgentDB.agent_id == permission.target_id
                    ).first()
                    if not target_agent:
                        raise ValueError(f"Target agent not found: {permission.target_id}")
                elif permission.type == PermissionType.ALLOW_PROVIDER:
                    # Check if target provider exists
                    target_provider = db.query(ProviderDB).filter(
                        ProviderDB.id == permission.target_id
                    ).first()
                    if not target_provider:
                        raise ValueError(f"Target provider not found: {permission.target_id}")
            
            # Convert permissions to a list of dictionaries for storage
            permission_dicts = []
            for permission in permissions:
                permission_dict = {
                    "type": permission.type.value,  # Store the enum value
                    "target_id": permission.target_id
                }
                permission_dicts.append(permission_dict)
            
            agent.permissions = permission_dicts
            agent.updated_at = datetime.now(timezone.utc)
            db.commit()
            
            # Decrypt sensitive fields before converting to Agent model
            try:
                if agent.dpop_public_key:
                    agent.dpop_public_key = encryption_manager.decrypt_field(agent.dpop_public_key)
                
            except Exception as e:
                log_service.log_event(
                    "field_decryption_error",
                    {"agent_id": agent_id, "error": str(e), "error_type": type(e).__name__},
                    level=LogLevel.ERROR
                )
            agent_model = Agent.model_validate(agent)
            return agent_model
        finally:
            db.close()

    def check_permission(
        self,
        from_agent: Agent,
        to_agent: Agent
    ) -> bool:
        """Check if from_agent can interact with to_agent"""

        db = SessionLocal()
        try:
            # Verify provider status if checking provider permission
            for permission in to_agent.permissions:
                if permission.type == PermissionType.ALLOW_AGENT:
                    if permission.target_id == str(from_agent.agent_id):
                        return True
                        
                elif permission.type == PermissionType.ALLOW_PROVIDER:
                    # Verify provider exists and is active
                    provider = db.query(ProviderDB).filter(
                        ProviderDB.id == from_agent.provider_id
                    ).first()
                    
                    if not provider:
                        return False
                        
                    if permission.target_id == str(from_agent.provider_id):
                        return True
            return False
        finally:
            db.close()

    def remove_permission(
        self,
        agent_id: str,
        permission: AgentPermission
    ) -> Agent:
        """Remove a permission from an agent"""
        db = SessionLocal()
        try:
            agent = db.query(AgentDB).filter(AgentDB.agent_id == agent_id).first()
            if not agent:
                raise ValueError("Agent not found")
            
            if not agent.permissions:
                raise ValueError("Agent has no permissions")
            
            # Remove the permission if it exists
            updated_permissions = [
                p for p in agent.permissions 
                if not (p["type"] == permission.type.value and 
                       p["target_id"] == permission.target_id)
            ]
            
            if len(updated_permissions) == len(agent.permissions):
                raise ValueError("Permission not found")
                
            agent.permissions = updated_permissions
            agent.updated_at = datetime.now(timezone.utc)
            db.commit()
            
            # Decrypt sensitive fields before converting to Agent model
            if agent.dpop_public_key:
                agent.dpop_public_key = encryption_manager.decrypt_field(agent.dpop_public_key)
            # Note: hashed_secret is not encrypted, it's a SHA-256 hash
            
            return Agent.model_validate(agent)
        finally:
            db.close()