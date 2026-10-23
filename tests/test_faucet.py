"""Tests for the Celo faucet service.

The faucet is reached over plain HTTP, so these tests drive it through an
``httpx.MockTransport`` rather than a mocking library: adding ``respx`` would
mean a lockfile change, and CI gates on ``uv lock --check``.
"""

import json

import httpx
import pytest

import celo_mcp.faucet.service as faucet_service
from celo_mcp.config import Settings
from celo_mcp.faucet import FaucetService

API_KEY = "cfk_prd_notarealkey_0123456789"
ADDRESS = "0x1234567890123456789012345678901234567890"
TX_HASH = "0x" + "ab" * 32
REQUEST_KEY = "-Oabc123def456"


@pytest.fixture(autouse=True)
def no_ambient_api_key(monkeypatch):
    """Keep a real key on the developer's machine from reaching these tests.

    FaucetService falls back to settings when no key is passed, so where a key
    is configured the "missing key" test would find one and never raise.
    Deleting the environment variable is not enough: Settings also reads a
    local .env, which survives monkeypatch.delenv. Replacing the lookup covers
    both sources.
    """
    monkeypatch.delenv("CELO_MCP_FAUCET_API_KEY", raising=False)
    monkeypatch.setattr(
        faucet_service,
        "get_settings",
        lambda: Settings(faucet_api_key=None, _env_file=None),
    )


def _service(handler, api_key=API_KEY):
    """Build a service whose HTTP calls are served by ``handler``.

    Poll timings are shortened so the waiting tests finish in milliseconds
    rather than the twenty seconds the real service allows.
    """
    service = FaucetService(api_key=api_key, transport=httpx.MockTransport(handler))
    service.poll_timeout = 0.5
    service.poll_interval = 0.01
    return service


def _json(status_code, payload, headers=None):
    return httpx.Response(status_code, json=payload, headers=headers or {})


async def test_request_without_wait_returns_pending_key():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return _json(200, {"status": "Pending", "key": REQUEST_KEY})

    result = await _service(handler).request_funds(ADDRESS, wait=False)

    assert seen["url"] == "https://faucet.celo.org/api/faucet"
    assert seen["auth"] == f"Bearer {API_KEY}"
    assert seen["body"] == {"beneficiary": ADDRESS, "network": "celo-sepolia"}
    assert result.status == "Pending"
    assert result.request_key == REQUEST_KEY
    assert result.beneficiary == ADDRESS
    assert result.network == "celo-sepolia"
    assert result.tx_hash is None
    assert result.error is None


async def test_request_waits_for_payout_and_returns_tx_hash():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/api/faucet":
            return _json(200, {"status": "Pending", "key": REQUEST_KEY})
        # First poll is still queued; the second one has landed.
        if calls.count("/api/status") == 1:
            return _json(200, {"status": "Working", "beneficiary": ADDRESS})
        return _json(200, {"status": "Done", "beneficiary": ADDRESS, "txHash": TX_HASH})

    result = await _service(handler).request_funds(ADDRESS)

    assert result.status == "Done"
    assert result.tx_hash == TX_HASH
    assert result.explorer_url == f"https://celo-sepolia.blockscout.com/tx/{TX_HASH}"
    assert result.request_key == REQUEST_KEY
    assert calls.count("/api/status") >= 2


async def test_request_poll_timeout_returns_key_without_raising():
    def handler(request):
        if request.url.path == "/api/faucet":
            return _json(200, {"status": "Pending", "key": REQUEST_KEY})
        return _json(200, {"status": "Pending", "beneficiary": ADDRESS})

    result = await _service(handler).request_funds(ADDRESS)

    assert result.status == "Pending"
    assert result.request_key == REQUEST_KEY
    assert result.tx_hash is None
    # The agent needs to be told how to pick the request back up.
    assert "get_faucet_request_status" in result.message


async def test_failed_payout_is_reported_not_polled_forever():
    def handler(request):
        if request.url.path == "/api/faucet":
            return _json(200, {"status": "Pending", "key": REQUEST_KEY})
        return _json(200, {"status": "Failed", "beneficiary": ADDRESS})

    result = await _service(handler).request_funds(ADDRESS)

    assert result.status == "Failed"
    assert result.tx_hash is None


async def test_missing_api_key_names_the_env_var_and_where_to_get_one():
    def handler(request):  # pragma: no cover - must never be reached
        raise AssertionError("no request should be made without an API key")

    with pytest.raises(ValueError) as exc_info:
        await _service(handler, api_key=None).request_funds(ADDRESS)

    message = str(exc_info.value)
    assert "CELO_MCP_FAUCET_API_KEY" in message
    assert "faucet.celo.org/keys" in message


async def test_invalid_address_raises_before_any_http_call():
    def handler(request):  # pragma: no cover - must never be reached
        raise AssertionError("invalid addresses must not reach the faucet")

    with pytest.raises(ValueError, match="Invalid address"):
        await _service(handler).request_funds("not-an-address")


async def test_unsupported_network_raises_before_any_http_call():
    def handler(request):  # pragma: no cover - must never be reached
        raise AssertionError("unsupported networks must not reach the faucet")

    with pytest.raises(ValueError, match="celo-sepolia"):
        await _service(handler).request_funds(ADDRESS, network="celo")


async def test_rate_limit_surfaces_error_code_and_retry_after():
    def handler(request):
        return _json(
            429,
            {
                "status": "Failed",
                "message": "Faucet limit exceeded",
                "error": "faucet_limit_exceeded",
            },
            headers={"Retry-After": "600"},
        )

    result = await _service(handler).request_funds(ADDRESS)

    assert result.status == "Failed"
    assert result.error is not None
    assert result.error.error_code == "faucet_limit_exceeded"
    assert result.error.retry_after_seconds == 600


async def test_invalid_key_surfaces_error_code():
    def handler(request):
        return _json(
            401,
            {
                "status": "Failed",
                "message": "Invalid or expired API key",
                "error": "invalid_api_key",
            },
        )

    result = await _service(handler).request_funds(ADDRESS)

    assert result.status == "Failed"
    assert result.error.error_code == "invalid_api_key"
    assert result.error.retry_after_seconds is None


async def test_api_key_never_reaches_the_result_or_the_logs(caplog):
    """The tool layer echoes results and errors straight back to the client.

    ``call_tool`` returns ``f"Error: {str(e)}"`` verbatim, so anything we put in
    a message or a log line can end up in the model's context.
    """

    def handler(request):
        return _json(
            401,
            {"status": "Failed", "message": "bad key", "error": "invalid_api_key"},
        )

    with caplog.at_level("DEBUG"):
        result = await _service(handler).request_funds(ADDRESS)

    assert API_KEY not in result.model_dump_json()
    assert API_KEY not in caplog.text


async def test_transport_failure_is_reported_as_unavailable(caplog):
    def handler(request):
        raise httpx.ConnectError("connection refused")

    with caplog.at_level("DEBUG"):
        result = await _service(handler).request_funds(ADDRESS)

    assert result.status == "Failed"
    assert result.error.error_code == "faucet_unavailable"
    assert API_KEY not in caplog.text


async def test_get_request_status_returns_tx_hash_and_explorer_url():
    def handler(request):
        assert request.url.path == "/api/status"
        assert dict(request.url.params) == {
            "key": REQUEST_KEY,
            "network": "celo-sepolia",
        }
        return _json(200, {"status": "Done", "beneficiary": ADDRESS, "txHash": TX_HASH})

    result = await _service(handler).get_request_status(REQUEST_KEY)

    assert result.status == "Done"
    assert result.beneficiary == ADDRESS
    assert result.tx_hash == TX_HASH
    assert result.explorer_url == f"https://celo-sepolia.blockscout.com/tx/{TX_HASH}"


async def test_get_request_status_handles_unknown_key():
    def handler(request):
        return _json(404, {"message": "No such request"})

    result = await _service(handler).get_request_status("nope")

    assert result.status == "Failed"
    assert result.error.error_code == "unknown_request"


async def test_get_request_status_needs_no_api_key():
    """``/api/status`` is unauthenticated, so a missing key must not block it."""

    def handler(request):
        assert request.headers.get("authorization") is None
        return _json(200, {"status": "Done", "beneficiary": ADDRESS, "txHash": TX_HASH})

    result = await _service(handler, api_key=None).get_request_status(REQUEST_KEY)

    assert result.status == "Done"
