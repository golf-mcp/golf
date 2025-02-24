import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple, List
from uuid import uuid4

from fastapi import HTTPException, Request, status

from ..core.config import get_settings
from ..core.logging.logging import log_service
from ..core.logging.models import LogLevel
from ..core.security.encryption import EncryptionManager
from ..db import SessionLocal
from ..db.models import AgentDB, ProviderDB
from ..models import Agent, AgentRegistration

encryption_manager = EncryptionManager()

class AgentService:
    def __init__(self):
        self.settings = get_settings()

    def create_agent_secret(self) -> str:
        """Generate a secure random secret for agent authentication"""
        return secrets.token_urlsafe(32)

    def hash_secret(self, secret: str) -> str:
        """Hash an agent secret for storage"""
        return hashlib.sha256(secret.encode()).hexdigest()
    
    def register_agent(
        self,
        registration: AgentRegistration
    ) -> Tuple[str, str]:
        """Register a new agent and return their credentials"""
        db = SessionLocal()
        try:
            # Check if provider exists
            provider = db.query(ProviderDB).filter(
                ProviderDB.id == str(registration.provider_id)
            ).first()
            
            if not provider:
                raise ValueError(f"Provider not found: {registration.provider_id}")
            
            # Generate agent secret
            agent_secret = self.create_agent_secret()
            hashed_secret = self.hash_secret(agent_secret)
            
            # Encrypt sensitive data
            encrypted_dpop_key = encryption_manager.encrypt_field(registration.dpop_public_key)
            
            # Create SQLAlchemy model instance
            db_agent = AgentDB(
                agent_id=str(uuid4()),
                provider_id=str(registration.provider_id),
                dpop_public_key=encrypted_dpop_key,
                name=f"agent-{uuid4().hex[:8]}", # Auto-generate name
                permissions=[],  # Empty list for initial permissions
                created_at=datetime.now(timezone.utc),
                hashed_secret=hashed_secret
            )
            
            db.add(db_agent)
            db.commit()
            db.refresh(db_agent)
            
            # Return just the agent_id and secret
            return db_agent.agent_id, agent_secret
            
        except ValueError as e:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()     
  
    async def get_current_agent(self, request: Request) -> Agent:
        """Get the current authenticated agent from headers"""
        agent_id = request.headers.get("agent-id")
        agent_secret = request.headers.get("agent-secret")
        
        if not agent_id or not agent_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing agent credentials"
            )
            
        agent = self.authenticate_agent(agent_id, agent_secret)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid agent credentials"
            )
            
        return agent

    def authenticate_agent(
        self,
        agent_id: str,
        agent_secret: str
    ) -> Optional[Agent]:
        """Authenticate an agent using their ID and secret"""
        db = SessionLocal()
        try:
            db_agent = db.query(AgentDB).filter(
                AgentDB.agent_id == agent_id
            ).first()
            
            if not db_agent:
                log_service.log_event(
                    "authentication_failed",
                    {"agent_id": agent_id, "reason": "agent_not_found"},
                    level=LogLevel.WARNING
                )
                return None

            hashed_secret = self.hash_secret(agent_secret)
            if db_agent.hashed_secret != hashed_secret:
                log_service.log_event(
                    "authentication_failed",
                    {"agent_id": agent_id, "reason": "invalid_secret"},
                    level=LogLevel.WARNING
                )
                return None

            # Decrypt sensitive data before returning
            decrypted_dpop_key = encryption_manager.decrypt_field(db_agent.dpop_public_key)
            
            # Update the DB model with decrypted data for Pydantic conversion
            db_agent.dpop_public_key = decrypted_dpop_key

            log_service.log_event(
                "authentication_successful",
                {"agent_id": agent_id}
            )
            return Agent.model_validate(db_agent)

        finally:
            db.close()

    def delete_agent(self, agent_id: str, provider_id: Optional[str] = None) -> bool:
        """Delete an agent from the registry
        
        Args:
            agent_id: The ID of the agent to delete
            provider_id: Optional provider ID to verify ownership
            
        Returns:
            bool: True if agent was deleted, False if agent was not found
            
        Raises:
            ValueError: If agent_id is invalid or if provider_id doesn't match agent's provider
            Exception: For any other errors during deletion
        """
        if not agent_id:
            raise ValueError("Agent ID is required")
            
        db = SessionLocal()
        try:
            # Find the agent
            db_agent = db.query(AgentDB).filter(
                AgentDB.agent_id == agent_id
            ).first()
            
            if not db_agent:
                return False
                
            # If provider_id is provided, verify ownership
            if provider_id and str(db_agent.provider_id) != str(provider_id):
                raise ValueError("Provider is not authorized to delete this agent")
                
            # Delete the agent
            db.delete(db_agent)
            db.commit()
            
            return True
            
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def get_provider_agents(
        self,
        provider_id: str,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False
    ) -> List[Agent]:
        """Get all agents for a specific provider
        
        Args:
            provider_id: The ID of the provider
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            include_inactive: Whether to include inactive agents
            
        Returns:
            List of Agent objects belonging to the provider
            
        Raises:
            ValueError: If provider_id is invalid
        """
        if not provider_id:
            raise ValueError("Provider ID is required")
            
        db = SessionLocal()
        try:
            # Verify provider exists
            provider = db.query(ProviderDB).filter(
                ProviderDB.id == str(provider_id)
            ).first()
            
            if not provider:
                raise ValueError(f"Provider not found: {provider_id}")
            
            # Build query
            query = db.query(AgentDB).filter(
                AgentDB.provider_id == str(provider_id)
            )
            
            # Add pagination
            query = query.offset(skip).limit(limit)
            
            # Execute query and convert to Agent models
            agents = []
            for db_agent in query.all():
                # Decrypt sensitive data
                if db_agent.dpop_public_key:
                    db_agent.dpop_public_key = encryption_manager.decrypt_field(db_agent.dpop_public_key)
                agents.append(Agent.model_validate(db_agent))
            
            return agents
            
        finally:
            db.close()

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID
        
        Args:
            agent_id: The ID of the agent to retrieve
            
        Returns:
            Optional[Agent]: The agent if found, None otherwise
        """
        db = SessionLocal()
        try:
            db_agent = db.query(AgentDB).filter(
                AgentDB.agent_id == agent_id
            ).first()
            
            if not db_agent:
                return None
                
            # Decrypt sensitive data before returning
            if db_agent.dpop_public_key:
                db_agent.dpop_public_key = encryption_manager.decrypt_field(db_agent.dpop_public_key)
                
            return Agent.model_validate(db_agent)
            
        finally:
            db.close()

