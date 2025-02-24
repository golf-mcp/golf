import os
from base64 import b64encode, b64decode
from datetime import datetime, UTC, timedelta
from typing import Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy.orm import Session

from ..config import get_settings
from ..logging.logging import log_service
from ...db.encryption_models import EncryptionKey as EncryptionKeyModel
from ...db.session import SessionLocal

class EncryptionKey:
    def __init__(self, key: bytes, salt: bytes, created_at: datetime):
        self.key = key
        self.salt = salt
        self.created_at = created_at
        self.fernet = Fernet(key)

class EncryptionManager:
    def __init__(self):
        self.settings = get_settings()
        self.keys: Dict[str, EncryptionKey] = {}
        self.current_key_id: Optional[str] = None
        self._initialized = False
        self.key_rotation_interval = timedelta(days=self.settings.KEY_ROTATION_DAYS)

    def _ensure_initialized(self):
        """Ensure keys are loaded before use"""
        if not self._initialized:
            self._load_or_create_keys()
            self._initialized = True

    def _load_or_create_keys(self):
        """Load existing keys from database or create new ones"""
        try:
            with SessionLocal() as db:
                # Load all active keys
                db_keys = db.query(EncryptionKeyModel).filter(
                    EncryptionKeyModel.is_active == True
                ).all()
                
                # Load keys into memory
                for db_key in db_keys:
                    self.keys[db_key.key_id] = EncryptionKey(
                        key=db_key.key,
                        salt=db_key.salt,
                        created_at=db_key.created_at
                    )
                    if db_key.is_current:
                        self.current_key_id = db_key.key_id
                
                log_service.log_event(
                    "keys_loaded",
                    {"key_count": len(self.keys)}
                )

                # Create new key if needed
                if not self.keys or self._should_rotate_key():
                    self._create_new_key(db)
                    
        except Exception as e:
            log_service.log_event(
                "key_load_error",
                {"error": str(e)},
                level="ERROR"
            )
            raise RuntimeError(f"Failed to load encryption keys: {str(e)}")

    def _create_new_key(self, db: Session):
        """Create a new encryption key and store in database"""
        try:
            # Generate new key with salt
            key_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            salt = os.urandom(16)
            key = Fernet.generate_key()
            
            # Create new key object
            new_key = EncryptionKey(
                key=key,
                salt=salt,
                created_at=datetime.now(UTC)
            )
            
            # Update current key in memory
            self.keys[key_id] = new_key
            old_current_id = self.current_key_id
            self.current_key_id = key_id
            
            # Update database
            if old_current_id:
                # Set old current key to not current
                db.query(EncryptionKeyModel).filter(
                    EncryptionKeyModel.key_id == old_current_id
                ).update({
                    "is_current": False
                })
            
            # Create new key in database
            db_key = EncryptionKeyModel(
                key_id=key_id,
                key=key,
                salt=salt,
                created_at=new_key.created_at,
                is_current=True
            )
            db.add(db_key)
            db.commit()
            
            log_service.log_event(
                "key_created",
                {"key_id": key_id}
            )
            
        except Exception as e:
            db.rollback()
            log_service.log_event(
                "key_creation_error",
                {"error": str(e)},
                level="ERROR"
            )
            raise RuntimeError(f"Failed to create new encryption key: {str(e)}")

    def _should_rotate_key(self) -> bool:
        """Check if the current key should be rotated"""
        # If key rotation is disabled, never rotate
        if not self.settings.KEY_ROTATION_ENABLED:
            return False
            
        # Otherwise check if we need to rotate based on age
        if not self.current_key_id:
            return True
        current_key = self.keys[self.current_key_id]
        return datetime.now(UTC) - current_key.created_at > self.key_rotation_interval

    def encrypt_field(self, data: str) -> str:
        """Encrypt a single field using the current key"""
        if not data:
            return data
        
        try:
            self._ensure_initialized()
            
            with SessionLocal() as db:
                if self._should_rotate_key():
                    self._create_new_key(db)
                
                current_key = self.keys[self.current_key_id]
                
                # Use both key and salt for encryption
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=current_key.salt,
                    iterations=100000,
                )
                derived_key = kdf.derive(current_key.key)
                fernet = Fernet(b64encode(derived_key))
                
                encrypted = fernet.encrypt(data.encode())
                return f"{self.current_key_id}:{b64encode(encrypted).decode('utf-8')}"
                
        except Exception as e:
            log_service.log_event(
                "encryption_error",
                {"error": str(e)},
                level="ERROR"
            )
            raise ValueError(f"Failed to encrypt data: {str(e)}")

    def decrypt_field(self, encrypted_data: str) -> str:
        """Decrypt a single field using the stored key"""
        if not encrypted_data:
            return encrypted_data
            
        try:
            self._ensure_initialized()
            
            key_id, data = encrypted_data.split(":", 1)
            
            # Load key if not in memory
            if key_id not in self.keys:
                with SessionLocal() as db:
                    db_key = db.query(EncryptionKeyModel).filter(
                        EncryptionKeyModel.key_id == key_id,
                        EncryptionKeyModel.is_active == True
                    ).first()
                    
                    if not db_key:
                        raise ValueError(f"Unknown or inactive key ID: {key_id}")
                        
                    self.keys[key_id] = EncryptionKey(
                        key=db_key.key,
                        salt=db_key.salt,
                        created_at=db_key.created_at
                    )
            
            key = self.keys[key_id]
            
            # Use both key and salt for decryption
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=key.salt,
                iterations=100000,
            )
            derived_key = kdf.derive(key.key)
            fernet = Fernet(b64encode(derived_key))
            
            decrypted = fernet.decrypt(b64decode(data.encode()))
            return decrypted.decode('utf-8')
            
        except Exception as e:
            log_service.log_event(
                "decryption_error",
                {"error": str(e)},
                level="ERROR"
            )
            raise ValueError(f"Failed to decrypt data: {str(e)}")

    def deactivate_key(self, key_id: str):
        """Deactivate an old encryption key"""
        try:
            self._ensure_initialized()
            
            with SessionLocal() as db:
                db.query(EncryptionKeyModel).filter(
                    EncryptionKeyModel.key_id == key_id
                ).update({
                    "is_active": False
                })
                db.commit()
                
                # Remove from memory if present
                if key_id in self.keys:
                    del self.keys[key_id]
                    
                log_service.log_event(
                    "key_deactivated",
                    {"key_id": key_id}
                )
                
        except Exception as e:
            log_service.log_event(
                "key_deactivation_error",
                {"error": str(e)},
                level="ERROR"
            )
            raise ValueError(f"Failed to deactivate key: {str(e)}")