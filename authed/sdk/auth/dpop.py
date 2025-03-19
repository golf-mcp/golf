"""DPoP (Demonstrating Proof of Possession) implementation."""

import uuid
import time
from cryptography.hazmat.primitives import serialization
import jwt

class DPoPHandler:
    """Handles DPoP proof creation."""
    
    def create_proof(self, method: str, url: str, private_key_pem: str) -> str:
        """Create a DPoP proof for a request.
        
        Args:
            method: HTTP method of the request
            url: Target URL of the request
            private_key_pem: PEM-encoded private key
            
        Returns:
            str: The DPoP proof JWT
        """
        # Load the private key
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None
        )
        
        # Create a secure nonce (32 characters)
        nonce = str(uuid.uuid4()) + str(uuid.uuid4())[:16]
        
        # Create the proof payload
        payload = {
            "jti": str(uuid.uuid4()),
            "htm": method.upper(),
            "htu": url,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,  # 5 minute expiry
            "nonce": nonce  # Add the nonce
        }
        
        # Create headers with key type and algorithm
        headers = {
            "typ": "dpop+jwt",
            "alg": "RS256",
            "jwk": {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256"
            }
        }
        
        # Add public key components to JWK
        public_key = private_key.public_key()
        public_numbers = public_key.public_numbers()
        headers["jwk"].update({
            "n": jwt.utils.base64url_encode(public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, byteorder='big')).decode('utf-8'),
            "e": jwt.utils.base64url_encode(public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, byteorder='big')).decode('utf-8')
        })
        
        # Create and sign the proof
        proof = jwt.encode(
            payload,
            private_key,
            algorithm="RS256",
            headers=headers
        )
        
        return proof 