"""Celo faucet service.

Requests testnet funds through the faucet's API-key path. The browser flow is
gated on reCAPTCHA v3, which scores headless callers badly and cannot be solved
without driving a real browser, so an API key is the only way an agent can
reach the faucet.

Nothing here touches an RPC endpoint: the faucet returns the payout transaction
hash itself, which is proof enough that the funds moved.
"""

import asyncio
import logging
import time

import httpx

from ..config import get_settings
from ..utils import validate_address
from .models import FaucetError, FaucetRequestResult, FaucetStatusResult

logger = logging.getLogger(__name__)

FAUCET_BASE_URL = "https://faucet.celo.org"
KEYS_URL = f"{FAUCET_BASE_URL}/keys"

# The faucet's own `networks` constant. Alfajores is not in it, and the API-key
# path refuses anything outside it, so this is an allowlist rather than a hint.
SUPPORTED_NETWORKS = ("celo-sepolia",)
DEFAULT_NETWORK = "celo-sepolia"

EXPLORER_URLS = {"celo-sepolia": "https://celo-sepolia.blockscout.com"}

HTTP_TIMEOUT_SECONDS = 15.0

# MCP gives a tool 30 seconds. Waiting 20 covers the common case where the
# payout lands while we are still in the call, and leaves room for the POST and
# the final poll to finish before the client gives up on us.
POLL_TIMEOUT_SECONDS = 20.0
POLL_INTERVAL_SECONDS = 2.0

TERMINAL_STATUSES = ("Done", "Failed")


class FaucetService:
    """Request testnet funds from the Celo faucet."""

    def __init__(
        self,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        """Initialize the faucet service.

        Args:
            api_key: Faucet API key. Defaults to the value of
                CELO_MCP_FAUCET_API_KEY. Never accept this from a tool
                argument: it would put the secret in the model's context and
                the conversation transcript on every call.
            transport: httpx transport override. Tests use this to serve the
                faucet from a mock instead of the network.
        """
        self.api_key = api_key if api_key is not None else get_settings().faucet_api_key
        self._transport = transport
        self.poll_timeout = POLL_TIMEOUT_SECONDS
        self.poll_interval = POLL_INTERVAL_SECONDS

    async def request_funds(
        self,
        beneficiary: str,
        network: str = DEFAULT_NETWORK,
        wait: bool = True,
    ) -> FaucetRequestResult:
        """Request testnet CELO for an address.

        Args:
            beneficiary: Address to fund.
            network: Testnet to fund on. Only celo-sepolia is supported.
            wait: Poll for the payout before returning, so the common case
                costs the caller a single round trip.

        Returns:
            The request outcome, including the payout transaction hash if it
            landed within the polling window.

        Raises:
            ValueError: The address is malformed, the network is unsupported,
                or no API key is configured.
        """
        self._check_network(network)
        if not validate_address(beneficiary):
            raise ValueError(f"Invalid address: {beneficiary}")
        if not self.api_key:
            raise ValueError(
                "No faucet API key configured. Set CELO_MCP_FAUCET_API_KEY to a "
                f"key created at {KEYS_URL} (sign in with GitHub)."
            )

        try:
            response = await self._post_request(beneficiary, network)
        except httpx.HTTPError as e:
            logger.error(f"Failed to reach the faucet: {e}")
            return FaucetRequestResult(
                status="Failed",
                beneficiary=beneficiary,
                network=network,
                error=FaucetError(
                    error_code="faucet_unavailable",
                    message=f"Could not reach the faucet: {e}",
                ),
            )

        if response.status_code >= 400:
            return FaucetRequestResult(
                status="Failed",
                beneficiary=beneficiary,
                network=network,
                error=self._error_from_response(response),
            )

        body = response.json()
        request_key = body.get("key")
        status = body.get("status", "Pending")

        if status in TERMINAL_STATUSES or not wait or not request_key:
            return FaucetRequestResult(
                status=status,
                beneficiary=beneficiary,
                network=network,
                request_key=request_key,
                message=self._pending_message(request_key)
                if status not in TERMINAL_STATUSES
                else None,
            )

        return await self._wait_for_payout(request_key, beneficiary, network)

    async def get_request_status(
        self, request_key: str, network: str = DEFAULT_NETWORK
    ) -> FaucetStatusResult:
        """Check on a faucet request that was still pending.

        Args:
            request_key: Key returned by request_funds.
            network: Testnet the request was made on.

        Returns:
            The current state of the request.

        Raises:
            ValueError: The network is unsupported.
        """
        self._check_network(network)

        try:
            response = await self._get_status(request_key, network)
        except httpx.HTTPError as e:
            logger.error(f"Failed to read faucet request status: {e}")
            return FaucetStatusResult(
                status="Failed",
                request_key=request_key,
                network=network,
                error=FaucetError(
                    error_code="faucet_unavailable",
                    message=f"Could not reach the faucet: {e}",
                ),
            )

        if response.status_code == 404:
            return FaucetStatusResult(
                status="Failed",
                request_key=request_key,
                network=network,
                error=FaucetError(
                    error_code="unknown_request",
                    message=(
                        f"The faucet has no request with key {request_key!r} on "
                        f"{network}."
                    ),
                ),
            )
        if response.status_code >= 400:
            return FaucetStatusResult(
                status="Failed",
                request_key=request_key,
                network=network,
                error=self._error_from_response(response),
            )

        body = response.json()
        tx_hash = body.get("txHash")
        return FaucetStatusResult(
            status=body.get("status", "Pending"),
            request_key=request_key,
            network=network,
            beneficiary=body.get("beneficiary"),
            tx_hash=tx_hash,
            explorer_url=self._explorer_url(network, tx_hash),
        )

    async def _wait_for_payout(
        self, request_key: str, beneficiary: str, network: str
    ) -> FaucetRequestResult:
        """Poll until the payout resolves or the window closes."""
        deadline = time.monotonic() + self.poll_timeout
        last: FaucetStatusResult | None = None

        while time.monotonic() < deadline:
            await asyncio.sleep(self.poll_interval)
            last = await self.get_request_status(request_key, network)
            if last.status in TERMINAL_STATUSES:
                return FaucetRequestResult(
                    status=last.status,
                    beneficiary=last.beneficiary or beneficiary,
                    network=network,
                    request_key=request_key,
                    tx_hash=last.tx_hash,
                    explorer_url=last.explorer_url,
                    error=last.error,
                )

        # Not an error: the faucet queue is simply slower than the window we
        # can hold an MCP call open for.
        return FaucetRequestResult(
            status=last.status if last else "Pending",
            beneficiary=beneficiary,
            network=network,
            request_key=request_key,
            message=self._pending_message(request_key),
        )

    async def _post_request(self, beneficiary: str, network: str) -> httpx.Response:
        async with self._client() as client:
            return await client.post(
                f"{FAUCET_BASE_URL}/api/faucet",
                json={"beneficiary": beneficiary, "network": network},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

    async def _get_status(self, request_key: str, network: str) -> httpx.Response:
        # /api/status is unauthenticated, so the key is deliberately not sent.
        async with self._client() as client:
            return await client.get(
                f"{FAUCET_BASE_URL}/api/status",
                params={"key": request_key, "network": network},
            )

    def _client(self) -> httpx.AsyncClient:
        kwargs = {"timeout": HTTP_TIMEOUT_SECONDS}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    @staticmethod
    def _check_network(network: str) -> None:
        if network not in SUPPORTED_NETWORKS:
            raise ValueError(
                f"Unsupported faucet network: {network}. The Celo faucet only "
                f"funds {', '.join(SUPPORTED_NETWORKS)}."
            )

    @staticmethod
    def _pending_message(request_key: str | None) -> str:
        if not request_key:
            return "The faucet accepted the request but returned no request key."
        return (
            "The payout is still queued. Call get_faucet_request_status with "
            f"request_key {request_key!r} to check whether it landed."
        )

    @staticmethod
    def _explorer_url(network: str, tx_hash: str | None) -> str | None:
        base = EXPLORER_URLS.get(network)
        if not base or not tx_hash:
            return None
        return f"{base}/tx/{tx_hash}"

    @staticmethod
    def _error_from_response(response: httpx.Response) -> FaucetError:
        """Turn a faucet error response into something an agent can act on."""
        try:
            body = response.json()
        except ValueError:
            body = {}

        retry_after = response.headers.get("Retry-After")
        try:
            retry_after_seconds = int(retry_after) if retry_after else None
        except ValueError:
            # Retry-After may be an HTTP date; no sensible integer to report.
            retry_after_seconds = None

        message = body.get("message") or f"Faucet returned HTTP {response.status_code}"
        error_code = body.get("error")
        if not error_code and response.status_code == 400:
            error_code = "bad_request"

        logger.error(
            f"Faucet request failed: HTTP {response.status_code} "
            f"({error_code or 'no error code'})"
        )
        return FaucetError(
            error_code=error_code,
            message=message,
            retry_after_seconds=retry_after_seconds,
        )
