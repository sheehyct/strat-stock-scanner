"""
JWT token validation middleware
Protects MCP endpoints with OAuth authentication
"""

from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from config import settings

security = HTTPBearer()
ALGORITHM = "HS256"


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """
    Validate JWT token from Authorization header

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is missing, invalid, or expired
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials

    try:
        # Decode and validate JWT
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        # Verify token type
        if payload.get("token_type") != "access":
            raise HTTPException(
                status_code=401,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Verify required claims
        if not payload.get("sub"):
            raise HTTPException(
                status_code=401,
                detail="Invalid token claims",
                headers={"WWW-Authenticate": "Bearer"}
            )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )

    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def optional_verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security, auto_error=False)
) -> dict:
    """
    Optional token validation (for endpoints that work with or without auth)

    Args:
        credentials: HTTP Bearer token credentials (optional)

    Returns:
        Decoded token payload or None if no token provided
    """
    if not credentials:
        return None

    return await verify_token(credentials)
