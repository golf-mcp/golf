import os
from functools import lru_cache
from typing import Optional

from pydantic import ConfigDict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    # JWT settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY")  # Use test-secret as default for testing
    
    # Internal API Key for service-to-service auth
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY")  # Must be set in production
    
    # CORS settings
    CORS_ORIGINS: list[str] = []
    CORS_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    CORS_HEADERS: list[str] = []
    CORS_CREDENTIALS: bool = True
    
    # Environment-specific settings
    ENV: str = os.getenv("ENV", "development")
    
    # Server settings
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    ALLOWED_HOSTS: list[str] = []
    
    # Rate limiting
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds
    RATE_LIMIT_DEFAULT: int = int(os.getenv("RATE_LIMIT_DEFAULT", "60"))
    RATE_LIMIT_TOKEN: int = int(os.getenv("RATE_LIMIT_TOKEN", "30"))
    RATE_LIMIT_VERIFY: int = int(os.getenv("RATE_LIMIT_VERIFY", "100"))
    RATE_LIMIT_REGISTER: int = int(os.getenv("RATE_LIMIT_REGISTER", "5"))
    
    # Validation settings
    MAX_NAME_LENGTH: int = 50
    MIN_NAME_LENGTH: int = 3
    ALLOWED_STATUSES: list[str] = ["active", "inactive", "suspended"]
    
    # Encryption settings
    ENCRYPTION_KEY: Optional[str] = os.getenv("ENCRYPTION_KEY")
    ENCRYPTED_FIELDS: list[str] = []
    
    # TLS Settings
    MIN_TLS_VERSION: str = "TLSv1.3"
    SECURE_CIPHERS: str = "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256"
    
    # Security Headers
    CSP_POLICY: str = ""
    
    # Database Pool Settings
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # 30 minutes
    
    # Encryption Settings
    KEY_ROTATION_ENABLED: bool = True
    KEY_ROTATION_DAYS: int = 30
    ENCRYPTION_KEY_STORE: str = "env"  # Options: env, vault (for production)
    MIN_KEY_SIZE: int = 2048
    
    # Database Encryption
    DB_ENCRYPTION_ENABLED: bool = True
    DB_ENCRYPTION_ALGORITHM: str = "AES256"
    DB_ENCRYPTION_KEY: Optional[str] = None
    
    
    # Security settings
    TOKEN_EXPIRY_MINUTES: int = 30
    KEY_DIRECTORY: str = "keys"
    
    # Redis settings for nonce cache
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    NONCE_TTL_SECONDS: int = 300  # 5 minutes
    
    # Logging
    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = True

    # Health check thresholds
    HEALTH_MEMORY_THRESHOLD: float = float(os.getenv("HEALTH_MEMORY_THRESHOLD", "85.0"))  # percent
    HEALTH_CPU_THRESHOLD: float = float(os.getenv("HEALTH_CPU_THRESHOLD", "90.0"))       # percent

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True
    )

@lru_cache()
def get_settings():
    return Settings() 