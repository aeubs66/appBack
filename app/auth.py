"""
Clerk JWT verification and authentication dependencies.
"""

import os
import httpx
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, jwk
from jose.utils import base64url_decode
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

security = HTTPBearer()

# Clerk configuration
CLERK_FRONTEND_API = os.getenv("CLERK_FRONTEND_API", "")

# JWKS URL and Issuer must be explicitly set or derived from instance name
# Format: https://{your-instance}.clerk.accounts.dev
CLERK_INSTANCE = os.getenv("CLERK_INSTANCE", "")  # e.g., "your-instance"
CLERK_JWKS_URL = os.getenv(
    "CLERK_JWKS_URL",
    f"https://{CLERK_INSTANCE}.clerk.accounts.dev/.well-known/jwks.json" if CLERK_INSTANCE else ""
)
CLERK_ISSUER = os.getenv(
    "CLERK_ISSUER",
    f"https://{CLERK_INSTANCE}.clerk.accounts.dev" if CLERK_INSTANCE else ""
)

# Validate configuration
if not CLERK_JWKS_URL or not CLERK_ISSUER:
    import warnings
    warnings.warn(
        "Clerk configuration incomplete. Set CLERK_JWKS_URL and CLERK_ISSUER, "
        "or set CLERK_INSTANCE in your .env file. "
        "Get these from your Clerk Dashboard > API Keys > JWT Template."
    )

# Cache for JWKS
_jwks_cache: Optional[dict] = None


async def get_jwks() -> dict:
    """Fetch and cache Clerk JWKS."""
    if not CLERK_JWKS_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Clerk JWKS URL not configured. Please set CLERK_JWKS_URL or CLERK_INSTANCE in .env file."
        )
    
    global _jwks_cache
    if _jwks_cache is None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(CLERK_JWKS_URL, timeout=10.0)
                response.raise_for_status()
                _jwks_cache = response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch Clerk JWKS from {CLERK_JWKS_URL}: {e.response.status_code} {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to connect to Clerk JWKS endpoint: {str(e)}"
            )
    return _jwks_cache


def get_public_key(token: str, jwks: dict) -> Optional[object]:
    """Get the public key for verifying the JWT token."""
    try:
        unverified_header = jwt.get_unverified_header(token)
        token_kid = unverified_header.get("kid")
    except jwt.JWTError:
        return None

    if not token_kid:
        return None

    # Find matching key
    matching_key = None
    for key in jwks.get("keys", []):
        if key.get("kid") == token_kid:
            matching_key = key
            break

    if not matching_key:
        return None

    try:
        # Log key info for debugging
        import logging
        logging.info(f"Found matching key: kid={matching_key.get('kid')}, kty={matching_key.get('kty')}, use={matching_key.get('use')}")
        
        # Construct public key - handle both RSA and EC keys
        key_type = matching_key.get("kty")
        
        if key_type == "RSA":
            # Ensure all required RSA fields are present
            if "n" not in matching_key or "e" not in matching_key:
                logging.error(f"RSA key missing required fields. Has 'n': {'n' in matching_key}, Has 'e': {'e' in matching_key}")
                return None
            rsa_key = {
                "kty": matching_key["kty"],
                "kid": matching_key["kid"],
                "use": matching_key.get("use", "sig"),
                "n": matching_key["n"],
                "e": matching_key["e"],
            }
            # Include 'alg' if present (required by jwk.construct)
            if "alg" in matching_key:
                rsa_key["alg"] = matching_key["alg"]
            public_key = jwk.construct(rsa_key)
            logging.info("Successfully constructed RSA public key")
            return public_key
        elif key_type == "EC":
            # For EC keys, use different format
            if "crv" not in matching_key or "x" not in matching_key or "y" not in matching_key:
                logging.error(f"EC key missing required fields. Has 'crv': {'crv' in matching_key}, Has 'x': {'x' in matching_key}, Has 'y': {'y' in matching_key}")
                return None
            ec_key = {
                "kty": matching_key["kty"],
                "kid": matching_key["kid"],
                "use": matching_key.get("use", "sig"),
                "crv": matching_key["crv"],
                "x": matching_key["x"],
                "y": matching_key["y"],
            }
            # Include 'alg' if present (required by jwk.construct)
            if "alg" in matching_key:
                ec_key["alg"] = matching_key["alg"]
            public_key = jwk.construct(ec_key)
            logging.info("Successfully constructed EC public key")
            return public_key
        else:
            # Try generic construction with the full key (includes all fields like 'alg')
            logging.info(f"Trying generic construction for key type: {key_type}")
            public_key = jwk.construct(matching_key)
            logging.info("Successfully constructed public key using generic method")
            return public_key
    except Exception as e:
        # Log the full error for debugging
        import logging
        import traceback
        logging.error(f"Failed to construct public key: {e}")
        logging.error(f"Key type: {matching_key.get('kty') if matching_key else 'None'}")
        logging.error(f"Key fields: {list(matching_key.keys()) if matching_key else 'None'}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return None


async def verify_clerk_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Verify Clerk JWT token and return clerk_user_id.
    
    Raises HTTPException if token is invalid.
    """
    import logging
    logging.basicConfig(level=logging.INFO)
    
    token = credentials.credentials
    logging.info(f"Received token (first 20 chars): {token[:20]}...")

    try:
        # Check configuration first
        if not CLERK_JWKS_URL or not CLERK_ISSUER:
            logging.error(f"CLERK_JWKS_URL: {CLERK_JWKS_URL}, CLERK_ISSUER: {CLERK_ISSUER}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Clerk configuration missing. Please set CLERK_JWKS_URL and CLERK_ISSUER in .env file."
            )
        
        # Decode token header to get kid (for debugging)
        try:
            unverified_header = jwt.get_unverified_header(token)
            token_kid = unverified_header.get("kid", "unknown")
        except Exception:
            token_kid = "unknown"
        
        # Get JWKS
        jwks = await get_jwks()
        
        # Get public key
        public_key = get_public_key(token, jwks)
        if not public_key:
            # Log available kids for debugging
            available_kids = [key.get("kid") for key in jwks.get("keys", [])]
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: Could not find matching key in JWKS. Token kid: {token_kid}, Available kids: {available_kids}",
            )

        # Decode token without verification first to see issuer
        try:
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            token_issuer = unverified_payload.get("iss", "unknown")
        except Exception:
            token_issuer = "unknown"

        # Verify token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=None,  # Clerk doesn't use audience
            issuer=CLERK_ISSUER,
            options={"verify_signature": True, "verify_iss": True, "verify_exp": True},
        )

        # Extract user ID
        clerk_user_id = payload.get("sub")
        if not clerk_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: No user ID found in token payload",
            )

        return clerk_user_id

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidIssuerError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token issuer. Token issuer: {token_issuer if 'token_issuer' in locals() else 'unknown'}, Expected: {CLERK_ISSUER}",
        )
    except jwt.JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_details = str(e)
        error_type = type(e).__name__
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed ({error_type}): {error_details}",
        )


# Dependency for protected routes
async def get_current_user(
    clerk_user_id: str = Depends(verify_clerk_token),
) -> str:
    """Dependency that returns the authenticated user's Clerk ID."""
    return clerk_user_id

