"""Database package initialization"""
from sqlalchemy.exc import SQLAlchemyError
# Import entire modules to ensure all models are registered
from . import models
from . import encryption_models
from .session import SessionLocal, init_db, get_db, engine
from .redis import get_redis_client

# Re-export commonly used classes
Base = models.Base
InteractionTokenDB = models.InteractionTokenDB
RevokedTokenDB = models.RevokedTokenDB
AgentDB = models.AgentDB
ProviderDB = models.ProviderDB
EncryptionKey = encryption_models.EncryptionKey

# Import all models to register them with SQLAlchemy metadata
__all__ = [
    'Base',
    'InteractionTokenDB',
    'RevokedTokenDB',
    'AgentDB',
    'ProviderDB',
    'SessionLocal',
    'init_db',
    'get_db',
    'get_redis_client',
    'EncryptionKey'
]

def initialize_models():
    """Initialize all database models"""
    try:
        # All models are already registered via the top-level imports
        # Create all tables using SQLAlchemy's built-in functionality
        Base.metadata.create_all(bind=engine)
        
        # Run migrations if needed
        try:
            from .migrations import run_all_migrations
            run_all_migrations()
        except ImportError:
            # Migrations package might not exist yet
            pass
            
        return True
    except SQLAlchemyError as e:
        print(f"Error creating tables: {str(e)}")
        raise