"""Validation utilities for URLs and other security-critical inputs"""
import re
from uuid import UUID
from typing import Optional

from .uri import is_uri


# Constants for validation
NAME_PATTERN = r"^[a-zA-Z0-9\s_-]{3,50}$"
KEY_MIN_LENGTH = 128  # Minimum length for public keys
KEY_MAX_LENGTH = 2048  # Maximum length for public keys

def sanitize_string(value: str, pattern: str, max_length: int = 50) -> str:
    """Sanitize a string input"""
    if not value or not isinstance(value, str):
        raise ValueError("Invalid string input")
    
    value = value.strip()
    if len(value) > max_length:
        raise ValueError(f"Input exceeds maximum length of {max_length}")
        
    if not re.match(pattern, value):
        raise ValueError("Input contains invalid characters")
    
    return value

def validate_public_key(key: str) -> str:
    """Validate public key format and length"""
    if not key or not isinstance(key, str):
        raise ValueError("Invalid public key")
        
    key = key.strip()
    if not (KEY_MIN_LENGTH <= len(key) <= KEY_MAX_LENGTH):
        raise ValueError(f"Public key must be between {KEY_MIN_LENGTH} and {KEY_MAX_LENGTH} characters")
        
    if not key.startswith("-----BEGIN PUBLIC KEY-----"):
        raise ValueError("Invalid public key format")
        
    return key

def validate_email(email: str) -> str:
    """Validate email format"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise ValueError("Invalid email format")
    return email.lower()

def validate_url(url: str) -> bool:
    """Validate URL format"""
    return bool(is_uri(url))

def validate_method(method: str) -> bool:
    """Validate HTTP method"""
    return method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]

def validate_agent_id(agent_id: str) -> Optional[UUID]:
    """Validate agent ID format"""
    try:
        return UUID(agent_id)
    except ValueError:
        raise ValueError("Invalid agent ID format") 