import os
from base64 import b64encode, b64decode

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ..config import get_settings
from ...core.logging.logging import log_service

class KeyManager:
    def __init__(self):
        self.settings = get_settings()
        self.private_key = None
        self.public_key = None
        self._encryption_key = None
        self._load_keys()

    def _load_keys(self):
        """Load keys from environment or k8s secrets"""
        try:
            # Try loading from k8s secrets first (mounted as env vars)
            private_key_data = os.getenv("REGISTRY_PRIVATE_KEY")
            public_key_data = os.getenv("REGISTRY_PUBLIC_KEY")
            encryption_key = os.getenv("REGISTRY_ENCRYPTION_KEY")

            if all([private_key_data, public_key_data, encryption_key]):
                # Load from k8s secrets (env vars)
                self.private_key = serialization.load_pem_private_key(
                    private_key_data.encode(),
                    password=None,
                    backend=default_backend()
                )
                self.public_key = serialization.load_pem_public_key(
                    public_key_data.encode(),
                    backend=default_backend()
                )
                self._encryption_key = b64decode(encryption_key)
                log_service.log_event("key_load", {"source": "kubernetes_secrets"})
            else:
                # Development/local environment - generate new keys
                self._generate_new_keys()
                log_service.log_event("key_load", {"source": "generated"})

        except Exception as e:
            log_service.log_event(
                "key_load_error",
                {"error": str(e)},
                level="ERROR"
            )
            raise RuntimeError(f"Failed to load encryption keys: {str(e)}")

    def _generate_new_keys(self):
        """Generate new keys - only for development"""
        if self.settings.ENV == "production":
            raise RuntimeError("Key generation not allowed in production")

        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.settings.MIN_KEY_SIZE,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        self._encryption_key = os.urandom(32)  # AES-256 key

        # Log the generated keys for local development setup
        if self.settings.ENV == "development":
            private_pem = self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            log_service.log_event(
                "development_keys_generated",
                {
                    "private_key": private_pem.decode(),
                    "public_key": public_pem.decode(),
                    "encryption_key": b64encode(self._encryption_key).decode()
                }
            )

    def get_private_key(self):
        return self.private_key

    def get_public_key(self):
        return self.public_key

    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data using AES-256-GCM"""
        if not data:
            return data
            
        try:
            iv = os.urandom(12)
            cipher = Cipher(
                algorithms.AES(self._encryption_key),
                modes.GCM(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(data.encode()) + encryptor.finalize()
            encrypted = iv + encryptor.tag + ciphertext
            return b64encode(encrypted).decode('utf-8')
            
        except Exception as e:
            log_service.log_event("encryption_error", {"error": str(e)}, level="ERROR")
            return data

    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data using AES-256-GCM"""
        if not encrypted_data:
            return encrypted_data
            
        try:
            encrypted = b64decode(encrypted_data)
            iv = encrypted[:12]
            tag = encrypted[12:28]
            ciphertext = encrypted[28:]
            
            cipher = Cipher(
                algorithms.AES(self._encryption_key),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext.decode('utf-8')
            
        except Exception as e:
            log_service.log_event("decryption_error", {"error": str(e)}, level="ERROR")
            return encrypted_data 