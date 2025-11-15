"""
Unit tests for OAuth 2.1 authentication
Tests authorization flow, token generation, and validation
"""

import pytest
from fastapi.testclient import TestClient
from server import app
import secrets


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


def test_protected_resource_metadata(client):
    """Test OAuth metadata endpoint"""
    response = client.get("/.well-known/oauth-protected-resource")

    assert response.status_code == 200, "Metadata endpoint should return 200"

    data = response.json()
    assert "authorization_servers" in data, "Should include authorization_servers"
    assert "bearer_methods_supported" in data, "Should include bearer_methods_supported"
    assert "scopes_supported" in data, "Should include scopes_supported"


def test_authorize_endpoint():
    """Test OAuth authorize endpoint"""
    client = TestClient(app)

    # Generate PKCE challenge
    code_verifier = secrets.token_urlsafe(32)
    import hashlib
    import base64
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip('=')

    response = client.get(
        "/authorize",
        params={
            "client_id": "test_client",
            "redirect_uri": "https://example.com/callback",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "response_type": "code",
            "scope": "mcp:read mcp:write"
        },
        follow_redirects=False
    )

    assert response.status_code == 307, "Should redirect to callback"
    assert "code=" in response.headers["location"], "Should include authorization code"


def test_health_endpoint(client):
    """Test health check endpoint"""
    response = client.get("/health")

    assert response.status_code == 200, "Health endpoint should return 200"

    data = response.json()
    assert data["status"] == "healthy", "Status should be healthy"
    assert "rate_limiter" in data, "Should report rate limiter status"


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")

    assert response.status_code == 200, "Root endpoint should return 200"

    data = response.json()
    assert "service" in data, "Should include service name"
    assert "version" in data, "Should include version"
    assert "features" in data, "Should list features"
    assert "endpoints" in data, "Should list endpoints"
