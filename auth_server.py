"""
OAuth 2.1 Authorization Server with PKCE
Implements MCP spec-compliant authentication
"""

from fastapi import APIRouter, HTTPException, Form, Query
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Optional
from datetime import datetime, timedelta
from jose import jwt
import secrets
import hashlib
import base64
from config import settings

router = APIRouter()

# In-memory storage for authorization codes and refresh tokens
# In production, use Redis or database
authorization_codes = {}
refresh_tokens = {}
ALGORITHM = "HS256"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token

    Args:
        data: Token payload data
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "token_type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create refresh token (longer-lived than access token)

    Args:
        data: Token payload data

    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "token_type": "refresh"
    })

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_pkce_challenge(verifier: str, challenge: str) -> bool:
    """
    Verify PKCE code challenge against verifier

    Args:
        verifier: Code verifier from token request
        challenge: Code challenge from authorization request

    Returns:
        True if verifier matches challenge (S256 method)
    """
    # S256: BASE64URL(SHA256(code_verifier))
    computed_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip('=')

    return computed_challenge == challenge


@router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_metadata():
    """
    OAuth Protected Resource Metadata endpoint
    Required by MCP specification for remote servers
    """
    return {
        "resource": f"http://localhost:{settings.PORT}",  # Will be replaced with actual Railway URL
        "authorization_servers": [f"http://localhost:{settings.PORT}"],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"http://localhost:{settings.PORT}/docs",
        "scopes_supported": ["mcp:read", "mcp:write"]
    }


@router.get("/authorize")
async def authorize(
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query(default="S256"),
    response_type: str = Query(default="code"),
    scope: Optional[str] = Query(default="mcp:read mcp:write"),
    state: Optional[str] = Query(default=None)
):
    """
    OAuth authorization endpoint

    Handles authorization requests from OAuth clients (Claude)
    Generates authorization code and redirects to callback

    Args:
        client_id: OAuth client identifier
        redirect_uri: Callback URI for authorization code
        code_challenge: PKCE code challenge (S256)
        code_challenge_method: Challenge method (must be S256)
        response_type: Must be 'code' for authorization code flow
        scope: Requested scopes (default: mcp:read mcp:write)
        state: Optional state parameter for CSRF protection

    Returns:
        Redirect to callback URI with authorization code
    """
    # Validate parameters
    if response_type != "code":
        raise HTTPException(status_code=400, detail="Only 'code' response type supported")

    if code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail="Only S256 PKCE method supported")

    # Generate authorization code
    auth_code = secrets.token_urlsafe(32)

    # Store authorization code with metadata
    authorization_codes[auth_code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "scope": scope,
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
        "used": False
    }

    # Build redirect URL
    redirect_url = f"{redirect_uri}?code={auth_code}"
    if state:
        redirect_url += f"&state={state}"

    return RedirectResponse(url=redirect_url)


@router.post("/token")
async def token(
    grant_type: str = Form(...),
    code: Optional[str] = Form(default=None),
    redirect_uri: Optional[str] = Form(default=None),
    code_verifier: Optional[str] = Form(default=None),
    refresh_token: Optional[str] = Form(default=None),
    client_id: Optional[str] = Form(default=None),
    client_secret: Optional[str] = Form(default=None)
):
    """
    OAuth token endpoint

    Exchanges authorization code for access token (authorization_code grant)
    or refresh token for new access token (refresh_token grant)

    Args:
        grant_type: 'authorization_code' or 'refresh_token'
        code: Authorization code (for authorization_code grant)
        redirect_uri: Must match original redirect_uri
        code_verifier: PKCE code verifier
        refresh_token: Refresh token (for refresh_token grant)
        client_id: OAuth client ID
        client_secret: OAuth client secret (optional)

    Returns:
        JSON with access_token, refresh_token, token_type, expires_in
    """
    if grant_type == "authorization_code":
        # Validate required parameters
        if not all([code, redirect_uri, code_verifier]):
            raise HTTPException(
                status_code=400,
                detail="Missing required parameters: code, redirect_uri, code_verifier"
            )

        # Validate authorization code
        if code not in authorization_codes:
            raise HTTPException(status_code=400, detail="Invalid authorization code")

        auth_data = authorization_codes[code]

        # Check if already used
        if auth_data["used"]:
            raise HTTPException(status_code=400, detail="Authorization code already used")

        # Check expiration
        if datetime.utcnow() > auth_data["expires_at"]:
            raise HTTPException(status_code=400, detail="Authorization code expired")

        # Verify redirect URI matches
        if redirect_uri != auth_data["redirect_uri"]:
            raise HTTPException(status_code=400, detail="Redirect URI mismatch")

        # Verify PKCE challenge
        if not verify_pkce_challenge(code_verifier, auth_data["code_challenge"]):
            raise HTTPException(status_code=400, detail="Invalid code verifier")

        # Mark code as used
        auth_data["used"] = True

        # Generate tokens
        token_data = {
            "sub": "user_id",  # In production, use actual user ID
            "client_id": auth_data["client_id"],
            "scope": auth_data["scope"]
        }

        access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(token_data)

        # Store refresh token
        refresh_tokens[new_refresh_token] = {
            "client_id": auth_data["client_id"],
            "scope": auth_data["scope"],
            "created_at": datetime.utcnow()
        }

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "scope": auth_data["scope"]
        }

    elif grant_type == "refresh_token":
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Missing refresh_token")

        # Validate refresh token
        try:
            payload = jwt.decode(
                refresh_token,
                settings.JWT_SECRET_KEY,
                algorithms=[ALGORITHM]
            )

            if payload.get("token_type") != "refresh":
                raise HTTPException(status_code=400, detail="Invalid token type")

            # Generate new access token
            token_data = {
                "sub": payload["sub"],
                "client_id": payload["client_id"],
                "scope": payload["scope"]
            }

            access_token = create_access_token(token_data)

            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "scope": payload["scope"]
            }

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=400, detail="Refresh token expired")
        except jwt.JWTError:
            raise HTTPException(status_code=400, detail="Invalid refresh token")

    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported grant_type. Use 'authorization_code' or 'refresh_token'"
        )
