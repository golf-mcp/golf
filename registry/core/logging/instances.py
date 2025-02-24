"""Shared instances for logging components"""
from .service import LogService
from .log_repository import LogRepository

# Create instances
log_repository = LogRepository()
log_service = LogService(log_repository) 