# Deploying the Celo MCP server (Streamable HTTP)

The HTTP transport is a standard container. It runs anywhere that runs a Docker image
and honours `$PORT`. Below is Google Cloud Run as the primary example; any container
host (Fly.io, Railway, Render, a VM) works the same way.

## The official instance

`https://mcp.celo.org/mcp` is a Cloud Run service in the project `celo-mcp-516015`
(region `europe-west1`), built from the `v0.5.0` tag with the Dockerfile in this repo.
Production settings:

| Setting | Value | Why |
| --- | --- | --- |
| `MCP_ALLOWED_HOSTS` | `mcp.celo.org` | DNS-rebinding protection stays on; the raw `*.run.app` hostname answers 421 |
| `MCP_TRUST_PROXY` | `2` | Google's frontend appends `<client>,<lb>`; the rate limiter keys on the client |
| `MCP_RATE_LIMIT` / `MCP_RATE_WINDOW` | `60` / `60` | per-instance, best effort |
| `MCP_CORS_ORIGINS` | `https://claude.ai` | the only browser origin that needs it |
| `MCP_AUTH_TOKEN` | unset | public, read-only data |
| `CELO_MCP_FAUCET_API_KEY` | unset | the faucet tools are not listed on the public instance |
| instances | min 1, max 3, 1 vCPU, 512 MiB | no cold start on the first call |

To ship a new version: tag a release, then redeploy from the tag with the same
`gcloud run deploy --source .` command and flags as below, swapping in the values
above. The domain mapping is created once by a verified `celo.org` owner and does
not need to be touched again.

## Run locally (no container)

```bash
celo-mcp-server --transport http --port 3000
curl http://127.0.0.1:3000/health
```

## Build and run the container

```bash
docker build -t celo-mcp:http .
docker run --rm -p 3000:3000 celo-mcp:http
curl http://127.0.0.1:3000/health
```

## Google Cloud Run

```bash
gcloud run deploy celo-mcp \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars MCP_TRANSPORT=http,MCP_ALLOWED_HOSTS=*
# Cloud Run injects $PORT automatically; the container binds to it.
```

`MCP_ALLOWED_HOSTS` matters: the SDK enables DNS-rebinding protection and rejects
requests whose `Host` header it does not recognise (HTTP 421). Either list the
service hostname (`MCP_ALLOWED_HOSTS=celo-mcp-xxxx.run.app`) or set `*` to disable
the check, which is reasonable for a public read-only endpoint behind the platform's
proxy. The Dockerfile defaults to `*` for this reason.

The service URL is your MCP endpoint at `https://<service-url>/mcp`.

### Locking it down (optional)

Set a bearer token so only clients with it can call tools:

```bash
gcloud run services update celo-mcp --set-env-vars MCP_AUTH_TOKEN=<random-token>
```

Clients then send `Authorization: Bearer <random-token>`. `/health` stays open for
Cloud Run's health checks.

The built-in rate limit (`MCP_RATE_LIMIT` / `MCP_RATE_WINDOW`) is **best-effort and per
instance** — with several instances running, each keeps its own counter. For hard
guarantees put a managed limiter (e.g. Cloud Armor) in front.

Behind a proxy — which is exactly what Cloud Run is — the peer address the server sees
is the platform's, so **every external caller would share a single bucket**: one noisy
client would rate-limit everyone, and a single agent making a burst of tool calls could
429 itself. Set `MCP_TRUST_PROXY` to the number of hops your infrastructure appends to
`X-Forwarded-For` so the limiter keys on the client instead:

```bash
gcloud run services update celo-mcp --set-env-vars MCP_TRUST_PROXY=2
```

**The count is what makes this safe, and it is counted from the right.** Proxies
*append* to `X-Forwarded-For`, and Google's frontend
[does not verify anything preceding](https://cloud.google.com/load-balancing/docs/https)
the `<client-ip>,<load-balancer-ip>` pair it adds — so the leftmost entry is simply
whatever the caller chose to send. Trusting it would let one client dodge the limit
entirely by varying that value per request. Only the trailing entries a hop of yours
wrote can be believed.

Pick the value by counting what sits in front of the container:

| Deployment | Value | Appended by the platform |
| --- | --- | --- |
| Single reverse proxy (nginx, Caddy) | `1` | `<client-ip>` |
| Google external Application Load Balancer | `2` | `<client-ip>,<lb-ip>` |
| No proxy — container exposed directly | unset | nothing; the peer address is the client |

If you are unsure, **err high**: too many hops falls back to the peer address, which is
merely the coarse one-shared-bucket behaviour, while too few hands the key to the caller.
To confirm what your deployment actually appends, send a request with a bogus leading
entry and look at what arrives:

```bash
curl -H 'X-Forwarded-For: 1.2.3.4' https://<your-service>/health
```

If the container sees `1.2.3.4, <your-ip>, …` then the platform appended two hops and
left the forgery in front, which is the case this setting exists to handle.

`/health` is always exempt so platform probes never consume a caller's budget.

## Fly.io (alternative)

```bash
fly launch --no-deploy       # generates fly.toml; set internal_port = 3000
fly deploy
```

## Verify any deployment

```bash
npx @modelcontextprotocol/inspector
# Transport: Streamable HTTP  ->  URL: https://<host>/mcp  ->  Connect -> List Tools
```

Expected: the same tool list the stdio server exposes.
