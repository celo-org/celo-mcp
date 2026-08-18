"""Security / operability tests for the HTTP transport.

NOTE: always use `with TestClient(build_app()) as client:`. Starlette only runs the
app's lifespan inside the context manager, and the SDK's lifespan is what starts the
streamable-http session manager. Without it, any request to /mcp raises instead of
returning a response.
"""

from starlette.testclient import TestClient

from celo_mcp.http_app import build_app


def test_health_ok():
    with TestClient(build_app()) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def _initialize_body():
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        },
    }


def test_dns_rebinding_protection_rejects_unknown_host():
    """The SDK's Host/Origin check is on by default and must stay on."""
    with TestClient(build_app()) as client:  # TestClient sends Host: testserver
        resp = client.post(
            "/mcp",
            json=_initialize_body(),
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert resp.status_code == 421, "unknown Host should be rejected"


def test_allowed_hosts_wildcard_disables_the_check(monkeypatch):
    """`MCP_ALLOWED_HOSTS=*` is the documented escape hatch for public deployments."""
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "*")
    with TestClient(build_app()) as client:
        resp = client.post(
            "/mcp",
            json=_initialize_body(),
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert resp.status_code == 200
    assert "serverInfo" in resp.text


def test_mcp_path_without_trailing_slash_is_not_redirected(monkeypatch):
    """Clients are configured with `/mcp` (no trailing slash) — it must serve directly.

    A path that 307-redirects costs a round trip and breaks any client that will not
    follow a redirect on POST.
    """
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "*")
    with TestClient(build_app()) as client:
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
            headers={"Accept": "application/json, text/event-stream"},
            follow_redirects=False,
        )
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}"
    assert "serverInfo" in resp.text


def test_cors_exposes_session_header():
    with TestClient(build_app()) as client:
        resp = client.options(
            "/mcp",
            headers={
                "Origin": "https://claude.ai",
                "Access-Control-Request-Method": "POST",
            },
        )
    # CORS middleware answers the preflight and echoes the allowed origin
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") in ("*", "https://claude.ai")


def test_rate_limit_returns_429(monkeypatch):
    # tiny window so the test is fast and deterministic
    monkeypatch.setenv("MCP_RATE_LIMIT", "3")
    monkeypatch.setenv("MCP_RATE_WINDOW", "60")
    with TestClient(build_app()) as client:
        codes = [client.get("/health").status_code for _ in range(5)]

    # first 3 allowed, then limited
    assert codes[:3] == [200, 200, 200]
    assert 429 in codes[3:]


def test_bearer_off_by_default_allows_health():
    with TestClient(build_app()) as client:
        assert client.get("/health").status_code == 200


def test_bearer_required_when_token_set(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "s3cret")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "*")
    # context manager is REQUIRED here: /mcp needs the lifespan (session manager) running
    with TestClient(build_app()) as client:
        # /health stays open even with auth on (needed for hosting health checks)
        assert client.get("/health").status_code == 200
        # /mcp without a token is rejected
        assert (
            client.post(
                "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}
            ).status_code
            == 401
        )
        # with the correct token it is not the auth layer that rejects it (not 401)
        ok = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={
                "Authorization": "Bearer s3cret",
                "Accept": "application/json, text/event-stream",
            },
        )
        assert ok.status_code != 401
