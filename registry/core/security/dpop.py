import hmac
import hashlib
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
from jwt import decode as jwt_decode, get_unverified_header
from jwt.exceptions import InvalidTokenError

from ..config import get_settings
from ..logging.logging import log_service
from ..logging.models import LogLevel
from ...db.redis import get_redis_client
from ...utils.validation import validate_url, validate_method

def normalize_url(url: str) -> str:
    """Normalize URL for comparison"""
    parsed = urlparse(url)
    
    # Fix duplicated port issue (e.g., localhost:8000:8000)
    netloc = parsed.netloc
    if netloc.count(':') > 1:
        # Extract hostname and first port
        parts = netloc.split(':')
        netloc = f"{parts[0]}:{parts[1]}"
        
    # Normalize port
    port = ""
    if ':' in netloc:
        hostname, port_str = netloc.split(':', 1)
        try:
            port_num = int(port_str)
            if port_num not in (80, 443):
                port = f":{port_num}"
            netloc = hostname
        except ValueError:
            # Invalid port, keep as is
            pass
            
    # Always use HTTPS for comparison since middleware enforces it
    return f"https://{netloc}{port}{parsed.path}"

class DPoPVerifier:
    def __init__(self):
        self.redis = get_redis_client()
        self.nonce_prefix = "dpop_nonce:"
        self.settings = get_settings()
        self.ALLOWED_ALGORITHMS = ["RS256"]
        self.MAX_CLOCK_SKEW = 300  # 5 minutes
    
    def hash_dpop_proof(self, proof: str) -> str:
        """Hash a DPoP proof for storage and comparison"""
        return hashlib.sha256(proof.encode()).hexdigest()
    
    def verify_proof(self, proof: str, dpop_public_key: str, http_method: str, url: str) -> bool:
        """Verify a DPoP proof"""
        try:
            log_service.log_event("dpop_verification_attempt", {
                "method": http_method,
                "url": url
            })

            # Validate inputs
            if not all([proof, dpop_public_key, http_method, url]):
                log_service.log_event(
                    "dpop_verification_error",
                    {"error": "Missing required parameters"},
                    level=LogLevel.ERROR
                )
                return False
            
            if not validate_method(http_method):
                log_service.log_event(
                    "invalid_method",
                    {"method": http_method},
                    level=LogLevel.ERROR
                )
                return False
            
            if not validate_url(url):
                log_service.log_event(
                    "invalid_url",
                    {"url": url},
                    level=LogLevel.ERROR
                )
                return False

            # Verify JWT header before decoding
            try:
                header = get_unverified_header(proof)
                if header.get("typ") != "dpop+jwt":
                    log_service.log_event(
                        "dpop_verification_error",
                        {"error": "Invalid typ claim in header"},
                        level=LogLevel.ERROR
                    )
                    return False
                if header.get("alg") not in self.ALLOWED_ALGORITHMS:
                    log_service.log_event(
                        "dpop_verification_error",
                        {"error": f"Algorithm {header.get('alg')} not allowed"},
                        level=LogLevel.ERROR
                    )
                    return False
            except Exception as e:
                log_service.log_event(
                    "dpop_verification_error",
                    {"error": f"Invalid JWT header: {str(e)}"},
                    level=LogLevel.ERROR
                )
                return False
            
            # Validate and format public key
            try:
                if not dpop_public_key.startswith('-----BEGIN PUBLIC KEY-----'):
                    dpop_public_key = f"-----BEGIN PUBLIC KEY-----\n{dpop_public_key}\n-----END PUBLIC KEY-----"
                if not dpop_public_key.strip().endswith('-----END PUBLIC KEY-----'):
                    raise ValueError("Invalid public key format")
            except Exception as e:
                log_service.log_event(
                    "dpop_verification_error",
                    {"error": f"Invalid public key format: {str(e)}"},
                    level=LogLevel.ERROR
                )
                return False
            
            try:
                decoded_proof = jwt_decode(
                    proof,
                    dpop_public_key,
                    algorithms=self.ALLOWED_ALGORITHMS,
                    options={"verify_signature": True}  # Always verify signature
                )
                log_service.log_event(
                    "dpop_proof_decoded",
                    {
                        "claims": {k: v for k, v in decoded_proof.items() if k not in ["nonce"]}
                    }
                )
            except InvalidTokenError as e:
                log_service.log_event(
                    "dpop_verification_error",
                    {"error": f"Invalid DPoP proof: {str(e)}"},
                    level=LogLevel.ERROR
                )
                return False
            
            # Verify required claims
            required_claims = ["jti", "htm", "htu", "iat"]
            if not all(claim in decoded_proof for claim in required_claims):
                missing = [claim for claim in required_claims if claim not in decoded_proof]
                log_service.log_event(
                    "dpop_verification_error",
                    {"error": f"Missing required claims: {missing}"},
                    level=LogLevel.ERROR
                )
                return False

            # Verify JTI is a valid UUID
            try:
                uuid.UUID(decoded_proof["jti"])
            except ValueError:
                log_service.log_event(
                    "dpop_verification_error",
                    {"error": "Invalid jti format - must be UUID"},
                    level=LogLevel.ERROR
                )
                return False

            # Verify timestamps
            if not self._verify_timestamps(decoded_proof):
                return False
            
            # Verify HTTP method and URL
            if not self._verify_method_and_url(decoded_proof, http_method, url):
                return False
            
            # Verify nonce (required)
            if "nonce" not in decoded_proof or not self._verify_nonce(decoded_proof["nonce"]):
                log_service.log_event(
                    "dpop_verification_error",
                    {"error": "Missing or invalid nonce"},
                    level=LogLevel.ERROR
                )
                return False
            
            return True
            
        except Exception as e:
            log_service.log_event(
                "dpop_verification_error",
                {"error": str(e)},
                level=LogLevel.ERROR
            )
            return False
    
    def _verify_timestamps(self, decoded_proof: dict) -> bool:
        """Verify the timestamps in the DPoP proof"""
        try:
            # Verify iat (issued at) claim
            if "iat" not in decoded_proof:
                log_service.log_event(
                    "dpop_verification_error",
                    {"error": "Missing iat claim"},
                    level=LogLevel.ERROR
                )
                return False

            # Verify timestamp with configurable clock skew
            now = datetime.now(timezone.utc).timestamp()
            if abs(decoded_proof["iat"] - now) > self.MAX_CLOCK_SKEW:
                log_service.log_event(
                    "dpop_timestamp_invalid",
                    {
                        "proof_time": decoded_proof["iat"],
                        "current_time": now,
                        "max_skew": self.MAX_CLOCK_SKEW
                    },
                    level=LogLevel.ERROR
                )
                return False

            return True
        except Exception as e:
            log_service.log_event(
                "dpop_verification_error",
                {"error": f"Timestamp verification failed: {str(e)}"},
                level=LogLevel.ERROR
            )
            return False
    
    def _verify_method_and_url(self, decoded_proof: dict, http_method: str, url: str) -> bool:
        """Verify the HTTP method and URL in the DPoP proof"""
        try:
            if "htm" not in decoded_proof or "htu" not in decoded_proof:
                log_service.log_event(
                    "dpop_verification_error",
                    {"error": "Missing htm or htu claim"},
                    level=LogLevel.ERROR
                )
                return False

            # Log both methods for debugging
            log_service.log_event(
                "dpop_method_comparison",
                {
                    "proof_method": decoded_proof["htm"],
                    "request_method": http_method
                }
            )

            # Use constant-time comparison for method
            if not hmac.compare_digest(decoded_proof["htm"].upper(), http_method.upper()):
                log_service.log_event(
                    "dpop_verification_error",
                    {
                        "error": "HTTP method mismatch",
                        "proof_method": decoded_proof["htm"],
                        "request_method": http_method
                    },
                    level=LogLevel.ERROR
                )
                return False

            # Normalize URLs before comparison
            normalized_proof_url = normalize_url(decoded_proof["htu"])
            normalized_request_url = normalize_url(url)
            
            # Log URLs for debugging
            log_service.log_event(
                "dpop_url_comparison",
                {
                    "proof_url": normalized_proof_url,
                    "request_url": normalized_request_url
                }
            )
            
            if not hmac.compare_digest(normalized_proof_url, normalized_request_url):
                log_service.log_event(
                    "dpop_verification_error",
                    {
                        "error": "URL mismatch",
                        "proof_url": normalized_proof_url,
                        "request_url": normalized_request_url
                    },
                    level=LogLevel.ERROR
                )
                return False

            return True
        except Exception as e:
            log_service.log_event(
                "dpop_verification_error",
                {"error": f"Method/URL verification failed: {str(e)}"},
                level=LogLevel.ERROR
            )
            return False
    
    def _verify_nonce(self, nonce: str) -> bool:
        """Verify the nonce in the DPoP proof"""
        try:
            # Validate nonce format (should be URL-safe base64)
            if not isinstance(nonce, str) or len(nonce) < 16:
                log_service.log_event(
                    "dpop_verification_error",
                    {"error": "Invalid nonce format"},
                    level=LogLevel.ERROR
                )
                return False

            # Check if nonce has been used before
            if self._is_nonce_used(nonce):
                log_service.log_event(
                    "dpop_verification_error",
                    {"error": "Nonce has already been used"},
                    level=LogLevel.ERROR
                )
                return False

            # Mark nonce as used
            self._mark_nonce_used(nonce)
            return True
        except Exception as e:
            log_service.log_event(
                "dpop_verification_error",
                {"error": f"Nonce verification failed: {str(e)}"},
                level=LogLevel.ERROR
            )
            return False
    
    def _is_nonce_used(self, nonce: str) -> bool:
        """Check if nonce has been used"""
        key = f"{self.nonce_prefix}{nonce}"
        return bool(self.redis.exists(key))
    
    def _mark_nonce_used(self, nonce: str):
        """Mark nonce as used"""
        key = f"{self.nonce_prefix}{nonce}"
        self.redis.setex(key, self.settings.NONCE_TTL_SECONDS, "1") 