"""Configuration settings for the registry service."""

import os
import json
from functools import lru_cache

class Settings:
    """Settings loaded from environment variables."""
    
    def __init__(self):
        # Server settings
        self.ENV = os.environ.get("ENV")
        self.HOST = os.environ.get("HOST")
        self.PORT = int(os.environ.get("PORT"))
        
        # Rate limiting
        self.RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW"))
        self.RATE_LIMIT_DEFAULT = int(os.environ.get("RATE_LIMIT_DEFAULT"))
        self.RATE_LIMIT_TOKEN = int(os.environ.get("RATE_LIMIT_TOKEN"))
        self.RATE_LIMIT_VERIFY = int(os.environ.get("RATE_LIMIT_VERIFY"))
        self.RATE_LIMIT_REGISTER = int(os.environ.get("RATE_LIMIT_REGISTER"))
        
        # Database settings
        self.DATABASE_URL = os.environ.get("DATABASE_URL")
        self.DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE"))
        self.DB_MAX_OVERFLOW = int(os.environ.get("DB_MAX_OVERFLOW"))
        self.DB_POOL_TIMEOUT = int(os.environ.get("DB_POOL_TIMEOUT"))
        self.DB_POOL_RECYCLE = int(os.environ.get("DB_POOL_RECYCLE"))
        
        # Redis settings
        self.REDIS_URL = os.environ.get("REDIS_URL")
        self.REDIS_DB = int(os.environ.get("REDIS_DB"))
        self.NONCE_TTL_SECONDS = int(os.environ.get("NONCE_TTL_SECONDS"))
        
        # Logging
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL")
        self.JSON_LOGS = os.environ.get("JSON_LOGS").lower() in ("true", "1", "t", "yes", "y")
        
        # CORS
        cors_origins = os.environ.get("CORS_ORIGINS")
        self.CORS_ORIGINS = self._parse_json_or_csv(cors_origins)
        
        cors_methods = os.environ.get("CORS_METHODS")
        self.CORS_METHODS = self._parse_json_or_csv(cors_methods)
        
        cors_headers = os.environ.get("CORS_HEADERS")
        self.CORS_HEADERS = self._parse_json_or_csv(cors_headers)
        
        self.CORS_CREDENTIALS = os.environ.get("CORS_CREDENTIALS").lower() in ("true", "1", "t", "yes", "y")
        
        # Security
        self.MIN_TLS_VERSION = os.environ.get("MIN_TLS_VERSION")
        self.SECURE_CIPHERS = os.environ.get("SECURE_CIPHERS")
        self.CSP_POLICY = os.environ.get("CSP_POLICY")
        
        allowed_hosts = os.environ.get("ALLOWED_HOSTS")
        self.ALLOWED_HOSTS = self._parse_json_or_csv(allowed_hosts)
        
        self.KEY_ROTATION_DAYS = int(os.environ.get("KEY_ROTATION_DAYS"))
        self.DB_ENCRYPTION_ENABLED = os.environ.get("DB_ENCRYPTION_ENABLED").lower() in ("true", "1", "t", "yes", "y")
        self.DB_ENCRYPTION_ALGORITHM = os.environ.get("DB_ENCRYPTION_ALGORITHM")
        self.TOKEN_EXPIRY_MINUTES = int(os.environ.get("TOKEN_EXPIRY_MINUTES"))
        self.MIN_KEY_SIZE = int(os.environ.get("MIN_KEY_SIZE"))
        
        # API keys
        self.INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")
        self.JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
        
        # Health checks
        self.HEALTH_CPU_THRESHOLD = int(os.environ.get("HEALTH_CPU_THRESHOLD"))
        self.HEALTH_MEMORY_THRESHOLD = int(os.environ.get("HEALTH_MEMORY_THRESHOLD"))
    
    def _parse_json_or_csv(self, value):
        """Parse a JSON string or comma-separated string into a list."""
        if not value:
            return []
            
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [item.strip() for item in value.split(",")]


@lru_cache()
def get_settings():
    """Get cached settings instance."""
    return Settings()