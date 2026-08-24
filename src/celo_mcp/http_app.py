"""Streamable HTTP transport for the Celo MCP server.

Serves the same `Server` instance the stdio transport uses, via the SDK's
`streamable_http_app()` (stateless, since this server is read-only), plus a
`/health` route and operational middleware: CORS, per-IP rate limiting, and
optional bearer auth.
"""

import hmac
import logging
import os
import time

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .server import init_services, server

logger = logging.getLogger(__name__)


async def _health(_request: Request) -> JSONResponse:
    return JSONResponse(
        {"status": "ok", "server": "celo-mcp", "transport": "streamable-http"}
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Best-effort per-client fixed-window rate limit (in-memory, per process).

    Not a distributed limiter: with multiple instances each holds its own window.
    Good enough to blunt naive floods on a public read-only endpoint; put a real
    limiter (Cloud Armor, Redis) in front for hard guarantees.

    Behind a proxy (Cloud Run, any load balancer) the peer address is the proxy, so
    every caller would share one bucket. Set `MCP_TRUST_PROXY` to the number of hops
    your infrastructure appends to `X-Forwarded-For` to key on the client instead.

    The count matters, and it is counted from the RIGHT: proxies *append*, and
    Google's frontend explicitly does not verify anything preceding the
    `<client-ip>,<lb-ip>` pair it adds. So the leftmost entry is whatever the caller
    chose to send, and keying on it would let one client mint a fresh bucket per
    request. Only the trailing entries a trusted hop wrote can be believed.

    Typical values: `1` for a single reverse proxy that appends the peer it saw
    (nginx, Caddy), `2` behind a Google external Application Load Balancer. Erring
    high is the safe direction — too many hops falls back to the peer address (one
    shared bucket, merely coarse), while too few reads a caller-written entry.

    `/health` is exempt so platform probes do not consume a caller's budget.
    """

    def __init__(self, app, limit: int, window: int, trusted_hops: int = 0):
        super().__init__(app)
        self.limit = limit
        self.window = window
        self.trusted_hops = trusted_hops
        self._hits: dict[str, tuple[int, float]] = {}

    def _client_key(self, request: Request) -> str:
        peer = request.client.host if request.client else "unknown"
        if self.trusted_hops:
            forwarded = request.headers.get("x-forwarded-for", "")
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            # count from the right: the trailing `trusted_hops` entries are the ones
            # our own infrastructure appended, and the first of those is the client
            if len(hops) >= self.trusted_hops:
                return hops[-self.trusted_hops]
            # a chain shorter than the trusted hops did not come through them
        return peer

    async def dispatch(self, request: Request, call_next):
        # platform health probes must not eat into anyone's budget
        if request.url.path == "/health":
            return await call_next(request)

        ip = self._client_key(request)
        now = time.monotonic()

        # purge expired windows so the dict cannot grow unbounded over time
        if len(self._hits) > 1024:
            self._hits = {
                k: v for k, v in self._hits.items() if now - v[1] < self.window
            }

        count, start = self._hits.get(ip, (0, now))
        if now - start >= self.window:
            count, start = 0, now
        count += 1
        self._hits[ip] = (count, start)

        if count > self.limit:
            return Response(
                '{"error":"rate_limited","hint":"Too many requests, slow down."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self.window)},
            )
        return await call_next(request)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Optional bearer auth. Enforced only when MCP_AUTH_TOKEN is set.

    /health is always open so hosting platforms can health-check the container.
    """

    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        header = request.headers.get("authorization", "")
        # constant-time compare so the token cannot be guessed by timing
        if not hmac.compare_digest(header, f"Bearer {self.token}"):
            return Response(
                '{"error":"unauthorized"}',
                status_code=401,
                media_type="application/json",
            )
        return await call_next(request)


def _transport_security(host: str) -> TransportSecuritySettings:
    """DNS-rebinding protection settings.

    The SDK enables this by default and rejects requests whose Host/Origin is not
    listed, which would reject every request to a deployed instance. Set
    `MCP_ALLOWED_HOSTS` to the public hostname(s), or to `*` to turn the check off
    (appropriate for a public read-only endpoint behind a trusted proxy).
    """
    configured = os.environ.get("MCP_ALLOWED_HOSTS", "").strip()

    if configured == "*":
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
            allowed_hosts=[],
            allowed_origins=[],
        )

    if configured:
        hosts = [h.strip() for h in configured.split(",") if h.strip()]
    else:
        # safe local default
        hosts = [f"{host}:*", "localhost:*", "127.0.0.1:*"]

    origins = [f"http://{h}" for h in hosts] + [f"https://{h}" for h in hosts]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def _trusted_proxy_hops() -> int:
    """Read MCP_TRUST_PROXY as a count of trusted `X-Forwarded-For` hops.

    Accepts a hop count; `true` is kept working as `1` and anything unparseable
    disables the feature rather than guessing, since guessing wrong on this value
    is what makes the header trustable when it should not be.
    """
    raw = os.environ.get("MCP_TRUST_PROXY", "").strip().lower()
    if not raw or raw in ("0", "false"):
        return 0
    if raw == "true":
        return 1
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning(
            "MCP_TRUST_PROXY=%r is not a hop count; ignoring it and keying the "
            "rate limiter on the peer address",
            raw,
        )
        return 0


def build_app(host: str = "127.0.0.1") -> Starlette:
    """Build the Starlette ASGI app exposing the MCP server over Streamable HTTP."""
    # Services are process-global and shared with the stdio transport; the SDK owns
    # this app's lifespan, so initialize them here rather than hooking into it.
    init_services()

    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,  # read-only server: no per-session state to keep
        custom_starlette_routes=[Route("/health", _health, methods=["GET"])],
        transport_security=_transport_security(host),
    )

    # Middleware order: CORS outermost, then rate limit, then optional auth.
    auth_token = os.environ.get("MCP_AUTH_TOKEN")
    if auth_token:
        app.add_middleware(BearerAuthMiddleware, token=auth_token)

    app.add_middleware(
        RateLimitMiddleware,
        limit=int(os.environ.get("MCP_RATE_LIMIT", "60")),
        window=int(os.environ.get("MCP_RATE_WINDOW", "60")),
        trusted_hops=_trusted_proxy_hops(),
    )

    cors_origins = os.environ.get("MCP_CORS_ORIGINS", "*")
    allow_origins = (
        ["*"]
        if cors_origins.strip() == "*"
        else [o.strip() for o in cors_origins.split(",")]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )

    return app
