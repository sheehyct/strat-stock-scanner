"""
Unit tests for OAuth 2.1 authentication
Tests authorization flow, token generation, and validation
"""

import base64
import hashlib
import secrets

import pytest
from fastapi.testclient import TestClient

from config import settings
from server import app


def _pkce_pair() -> tuple[str, str]:
    """Return (verifier, S256 challenge)."""
    verifier = secrets.token_urlsafe(32)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


@pytest.fixture
def strict_oauth(monkeypatch):
    """Force strict OAuth validation for the test, with a known good
    client_id/secret/redirect_uri allow-list pair."""
    monkeypatch.setattr(settings, "STRICT_OAUTH_VALIDATION", True)
    monkeypatch.setattr(settings, "OAUTH_CLIENT_ID", "claude-mcp-client")
    monkeypatch.setattr(settings, "OAUTH_CLIENT_SECRET", "test-secret-value")
    monkeypatch.setattr(
        settings,
        "OAUTH_REDIRECT_URI_ALLOWLIST",
        "https://claude.ai/api/mcp/auth_callback,https://example.com/callback",
    )


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def authorize_params():
    """Baseline /authorize query params; tests override fields they
    care about."""
    _verifier, challenge = _pkce_pair()
    return {
        "client_id": "claude-mcp-client",
        "redirect_uri": "https://example.com/callback",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "response_type": "code",
        "scope": "mcp:read mcp:write",
    }


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


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")

    assert response.status_code == 200, "Root endpoint should return 200"

    data = response.json()
    assert "service" in data, "Should include service name"
    assert "version" in data, "Should include version"
    assert "tools" in data, "Should list tools"
    assert "endpoints" in data, "Should list endpoints"


# --- OAuth client validation (log-only mode = default) ---------------------


def test_authorize_log_only_mode_accepts_unknown_client_id(client, authorize_params):
    """With STRICT_OAUTH_VALIDATION=False (default), a mismatched client_id
    must still complete the redirect. This is the safe-rollout default."""
    authorize_params["client_id"] = "unknown-client"
    response = client.get("/authorize", params=authorize_params, follow_redirects=False)
    assert response.status_code == 307
    assert "code=" in response.headers["location"]


def test_authorize_log_only_mode_accepts_offlist_redirect_uri(
    client, authorize_params, monkeypatch
):
    """Even with an allow-list configured, log-only mode still serves
    requests with an off-list redirect_uri (it just logs a warning)."""
    monkeypatch.setattr(
        settings,
        "OAUTH_REDIRECT_URI_ALLOWLIST",
        "https://only-this.example.com/cb",
    )
    authorize_params["redirect_uri"] = "https://something-else.example.com/cb"
    response = client.get("/authorize", params=authorize_params, follow_redirects=False)
    assert response.status_code == 307


# --- OAuth client validation (strict mode) ---------------------------------


def test_authorize_strict_accepts_matching_client(
    client, authorize_params, strict_oauth
):
    """In strict mode, the configured client_id + allow-listed redirect_uri
    must still produce a 307 redirect with an auth code."""
    response = client.get("/authorize", params=authorize_params, follow_redirects=False)
    assert response.status_code == 307
    assert "code=" in response.headers["location"]


def test_authorize_strict_rejects_unknown_client_id(
    client, authorize_params, strict_oauth
):
    """Unknown client_id should produce an RFC 6749 invalid_client error
    with HTTP 401 + WWW-Authenticate header."""
    authorize_params["client_id"] = "not-our-client"
    response = client.get("/authorize", params=authorize_params, follow_redirects=False)
    assert response.status_code == 401
    body = response.json()
    assert body["error"] == "invalid_client"
    assert "error_description" in body
    assert response.headers.get("www-authenticate") == "Bearer"


def test_authorize_strict_rejects_offlist_redirect_uri(
    client, authorize_params, strict_oauth
):
    """An off-list redirect_uri should produce an RFC 6749 invalid_request
    error with HTTP 400."""
    authorize_params["redirect_uri"] = "https://attacker.example.com/cb"
    response = client.get("/authorize", params=authorize_params, follow_redirects=False)
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "invalid_request"


def test_authorize_strict_no_allowlist_skips_redirect_check(
    client, authorize_params, strict_oauth, monkeypatch
):
    """When the allow-list is unset, the redirect_uri check is a no-op
    even in strict mode (operator opted out of the rule)."""
    monkeypatch.setattr(settings, "OAUTH_REDIRECT_URI_ALLOWLIST", None)
    authorize_params["redirect_uri"] = "https://anywhere.example.com/cb"
    response = client.get("/authorize", params=authorize_params, follow_redirects=False)
    assert response.status_code == 307


def test_token_strict_rejects_wrong_client_secret(
    client, authorize_params, strict_oauth
):
    """A confidential-client token request with the wrong secret should
    produce invalid_client / 401."""
    verifier, challenge = _pkce_pair()
    authorize_params["code_challenge"] = challenge
    auth_response = client.get(
        "/authorize", params=authorize_params, follow_redirects=False
    )
    assert auth_response.status_code == 307
    code = auth_response.headers["location"].split("code=", 1)[1].split("&", 1)[0]

    response = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": authorize_params["redirect_uri"],
            "code_verifier": verifier,
            "client_id": "claude-mcp-client",
            "client_secret": "wrong-secret",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"


def test_token_strict_accepts_public_client_without_secret(
    client, authorize_params, strict_oauth
):
    """Public-client flow (no client_secret on the request) must still
    succeed in strict mode - PKCE provides proof of possession. This is
    the spec-correct behavior for MCP clients that don't send a secret."""
    verifier, challenge = _pkce_pair()
    authorize_params["code_challenge"] = challenge
    auth_response = client.get(
        "/authorize", params=authorize_params, follow_redirects=False
    )
    code = auth_response.headers["location"].split("code=", 1)[1].split("&", 1)[0]

    response = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": authorize_params["redirect_uri"],
            "code_verifier": verifier,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_token_strict_accepts_matching_client_secret(
    client, authorize_params, strict_oauth
):
    """Confidential-client flow with the correct secret succeeds."""
    verifier, challenge = _pkce_pair()
    authorize_params["code_challenge"] = challenge
    auth_response = client.get(
        "/authorize", params=authorize_params, follow_redirects=False
    )
    code = auth_response.headers["location"].split("code=", 1)[1].split("&", 1)[0]

    response = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": authorize_params["redirect_uri"],
            "code_verifier": verifier,
            "client_id": "claude-mcp-client",
            "client_secret": "test-secret-value",
        },
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_authorize_logs_mismatch_in_permissive_mode(
    client, authorize_params, caplog
):
    """The whole point of log-only mode is to surface what claude.ai
    actually sends. Verify the warning fires."""
    import logging

    authorize_params["client_id"] = "captured-from-real-traffic"
    with caplog.at_level(logging.WARNING, logger="auth_server"):
        response = client.get(
            "/authorize", params=authorize_params, follow_redirects=False
        )
    assert response.status_code == 307
    assert any(
        "oauth_client_id_mismatch" in record.message for record in caplog.records
    ), f"Expected oauth_client_id_mismatch warning, got: {[r.message for r in caplog.records]}"
