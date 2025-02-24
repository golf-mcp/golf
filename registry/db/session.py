import time
from typing import Dict, Any

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import text

from ..core.config import get_settings

Base = declarative_base()

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def check_database_health() -> Dict[str, Any]:
    """Check PostgreSQL database connectivity"""
    try:
        start_time = time.perf_counter()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "healthy",
            "latency_ms": latency
        }
    except SQLAlchemyError as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        } 