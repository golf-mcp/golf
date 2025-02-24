import secrets
import uuid
from datetime import UTC, datetime
from typing import Dict, List, Optional
from pydantic import UUID4
from ..core.logging.logging import log_service
from ..core.logging.models import LogLevel, SecurityEvent
from ..core.security.key_manager import KeyManager
from ..db.models import AgentDB, ProviderDB
from ..db.session import SessionLocal
from ..models import Agent, Provider, ProviderUpdate

key_manager = KeyManager()

class ProviderService:
    def register_provider(
        self, 
        name: str,
        contact_email: str,
        registered_user_id: Optional[str] = None
    ) -> Provider:
        """Register a new provider"""
        try:
            provider_id = str(uuid.uuid4())
            provider_secret = secrets.token_urlsafe(32)
            
            log_service.log_event(
                "provider_registration_debug",
                {
                    "step": "creating_provider_model",
                    "provider_details": {
                        "id": provider_id,
                        "name": name
                    }
                },
                level=LogLevel.INFO
            )
            
            provider = Provider(
                id=provider_id,
                name=name,
                contact_email=contact_email,
                registered_user_id=registered_user_id,
                created_at=datetime.now(UTC),
                provider_secret=provider_secret
            )
            
            db = SessionLocal()
            try:
                log_service.log_event(
                    "provider_registration_debug",
                    {
                        "step": "creating_db_model",
                        "provider_id": provider_id
                    },
                    level=LogLevel.INFO
                )
                
                db_provider = ProviderDB(
                    id=provider_id,
                    name=name,
                    contact_email=contact_email,
                    created_at=provider.created_at,
                    provider_secret=provider_secret
                )
                db.add(db_provider)
                db.commit()
                
                # Convert the model dump to a dict and handle datetime serialization
                provider_dict = provider.model_dump()
                provider_dict["created_at"] = provider_dict["created_at"].isoformat()
                if provider_dict.get("updated_at"):
                    provider_dict["updated_at"] = provider_dict["updated_at"].isoformat()
                
                log_service.log_event(
                    "provider_registration_debug",
                    {
                        "step": "returning_provider",
                        "provider_id": provider_dict["id"]
                    },
                    level=LogLevel.INFO
                )
                
                # Return the original provider model that includes the secret
                return provider
            finally:
                db.close()
        except ValueError as e:
            # Re-raise validation errors with descriptive messages
            log_service.log_event(
                "provider_registration_error",
                {
                    "step": "validation_error",
                    "error_details": {
                        "message": str(e)
                    }
                },
                level=LogLevel.ERROR
            )
            raise ValueError(f"Invalid provider data: {str(e)}")
        except Exception as e:
            log_service.log_event(
                "provider_registration_error",
                {
                    "step": "unexpected_error",
                    "error_details": {
                        "message": str(e),
                        "type": type(e).__name__
                    }
                },
                level=LogLevel.ERROR
            )
            raise  # Let the actual error propagate up

    def update_provider(
        self,
        provider_id: UUID4,
        updates: ProviderUpdate
    ) -> Provider:
        """Update a provider's details"""
        db = SessionLocal()
        try:
            provider = db.query(ProviderDB).filter(
                ProviderDB.id == provider_id
            ).first()
            if not provider:
                raise ValueError(f"Provider {provider_id} not found")

            # Convert updates to dict and handle datetime fields
            update_dict = updates.model_dump(exclude_unset=True)
            if "updated_at" in update_dict:
                update_dict["updated_at"] = update_dict["updated_at"].isoformat()

            # Log the update attempt
            log_service.log_event(
                "provider_update",
                {
                    "actor_id": provider_id,  # The provider making the change
                    "resource_type": "provider",
                    "resource_id": provider_id,
                    "changes": update_dict
                },
                level=LogLevel.INFO
            )

            # Update fields
            for field, value in updates.model_dump(exclude_unset=True).items():
                setattr(provider, field, value)
            
            provider.updated_at = datetime.now(UTC)
            db.commit()
            return Provider.model_validate(provider)
            
        except Exception as e:
            log_service.log_event(
                "provider_update_failed",
                {
                    "error_details": {
                        "message": str(e),
                        "provider_id": provider_id
                    }
                },
                level=LogLevel.ERROR
            )
            raise
        finally:
            db.close()

    def get_provider(self, provider_id: UUID4) -> Optional[Provider]:
        """Get provider by ID"""
        db = SessionLocal()
        try:
            provider = db.query(ProviderDB).filter(
                ProviderDB.id == provider_id
            ).first()
            
            if provider:
                return Provider(
                    id=provider.id,
                    name=provider.name,
                    contact_email=provider.contact_email,
                    created_at=provider.created_at,
                    updated_at=provider.updated_at,
                    provider_secret=provider.provider_secret
                )
            return None
        finally:
            db.close()

    def get_provider_agents(self, provider_id: UUID4) -> List[Agent]:
        """Get all agents for a provider"""
        db = SessionLocal()
        try:
            # First check if the provider exists
            provider = db.query(ProviderDB).filter(
                ProviderDB.id == provider_id
            ).first()
            
            log_service.log_event(
                "provider_agents_debug",
                {
                    "step": "checking_provider",
                    "provider_id": provider_id,
                    "provider_exists": provider is not None
                },
                level=LogLevel.INFO
            )
            
            if not provider:
                raise ValueError(f"Provider {provider_id} not found")
            
            # Query agents (provider_id is already a string)
            agents = db.query(AgentDB).filter(
                AgentDB.provider_id == provider_id
            ).all()
            
            log_service.log_event(
                "provider_agents_debug",
                {
                    "step": "querying_agents",
                    "provider_id": provider_id,
                    "agent_count": len(agents)
                },
                level=LogLevel.INFO
            )
            
            # Decrypt sensitive fields before converting to Pydantic models
            for agent in agents:
                agent.dpop_public_key = key_manager.decrypt_data(agent.dpop_public_key)
                agent.public_key = key_manager.decrypt_data(agent.public_key)
                agent.hashed_secret = key_manager.decrypt_data(agent.hashed_secret)
            
            # Convert to Pydantic models
            return [Agent.model_validate(agent) for agent in agents]
        finally:
            db.close()

    def get_provider_stats(self, provider_id: UUID4) -> Dict:
        """Get provider dashboard stats"""
        db = SessionLocal()
        try:
            provider = db.query(ProviderDB).filter(
                ProviderDB.id == provider_id
            ).first()
            
            if not provider:
                raise ValueError(f"Provider {provider_id} not found")

            # Get agent counts
            agents = db.query(AgentDB).filter(
                AgentDB.provider_id == provider_id
            ).all()
            
            
            # Get recent interactions from logs
            recent_events = db.query(SecurityEvent).filter(
                SecurityEvent.details.op('->>')('provider_id') == provider_id
            ).order_by(
                SecurityEvent.timestamp.desc()
            ).limit(10).all()

            return {
                "total_agents": len(agents),
                "total_interactions": len(recent_events),
                "recent_events": [
                    {
                        "timestamp": event.timestamp.isoformat(),
                        "event_type": event.event_type,
                        "details": event.details
                    }
                    for event in recent_events
                ]
            }
        finally:
            db.close()

    def get_provider_by_secret(self, provider_secret: str) -> Optional[Provider]:
        """Get provider by their secret
        
        Args:
            provider_secret: The provider's secret key
            
        Returns:
            Optional[Provider]: The provider if found and secret matches, None otherwise
        """
        if not provider_secret:
            return None
            
        db = SessionLocal()
        try:
            provider = db.query(ProviderDB).filter(
                ProviderDB.provider_secret == provider_secret
            ).first()
            
            if provider:
                return Provider(
                    id=provider.id,
                    name=provider.name,
                    contact_email=provider.contact_email,
                    created_at=provider.created_at,
                    updated_at=provider.updated_at,
                    provider_secret=provider.provider_secret
                )
            return None
        finally:
            db.close() 