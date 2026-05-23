# STRAT Stock Scanner - Railway Deployment Guide

This guide covers a fresh Railway deployment of the scanner from a GitHub
clone. For ongoing operational notes (current URL, last known healthy
state, blockers) see `docs/SCANNER_STATUS_BRIEF.md`.

## What You're Deploying

MCP server with seven tools:

| Tool | Purpose |
|------|---------|
| `get_stock_quote` | Real-time bid/ask snapshot |
| `get_multiple_quotes` | Bulk quote lookup |
| `analyze_strat_patterns` | Deep STRAT analysis on a single symbol |
| `analyze_tfc` | Multi-timeframe TFC scoring for a single symbol |
| `scan_sector_for_strat` | Scan a sector universe for existing patterns |
| `scan_etf_holdings_strat` | Scan ETF holdings (SPY, QQQ, IWM, etc.) |
| `scan_for_tfc_alignment` | Scan a universe for TFC-aligned setups |

STRAT patterns detected:

- 2-1-2 Reversals (high confidence)
- 3-1-2 Continuations (high confidence)
- 2-2 Combos (medium confidence)
- Inside Bar Setups (low confidence; watch for breakout)

Data provider: Tradier Market Data REST API (consolidated real-time tape).
Bearer-token authentication via a single `TRADIER_API_TOKEN`.

## Required Files (already in the repo)

- `server.py` - MCP server (FastAPI + official MCP SDK with SSE transport)
- `tradier_client.py` - Async Tradier client with normalization + rate
  limiter integration
- `mcp_tools.py` - The seven tool implementations
- `strat_detector.py` - STRAT classification + pattern detection
- `rate_limiter.py` - Generic async rate limiter
- `auth_server.py` + `auth_middleware.py` - OAuth 2.1 with PKCE
- `config.py` - Pydantic-settings env loader
- `requirements.txt` - Python deps (pinned)
- `railway.json` - Railway service configuration

## Deploy to Railway

### Step 1: Create the Railway service

1. Sign in to https://railway.app
2. **New Project** -> **Deploy from GitHub repo** -> select the
   `strat-stock-scanner` repo
3. Railway auto-detects Python via NIXPACKS and starts the first build

### Step 2: Configure environment variables

In the Railway dashboard, open the service -> **Variables** tab -> add:

```
# Tradier (required)
TRADIER_API_TOKEN=<your-tradier-production-bearer-token>

# OAuth (required - generate locally with secrets.token_urlsafe(32))
JWT_SECRET_KEY=<random-32-byte-urlsafe-string>
OAUTH_CLIENT_SECRET=<random-32-byte-urlsafe-string>

# Server URL (REQUIRED - must match Railway's serving domain so OAuth
# discovery returns the correct resource URL to MCP clients)
SERVER_URL=https://<your-railway-app>.up.railway.app
```

Generate the OAuth secrets locally:

```bash
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('OAUTH_CLIENT_SECRET=' + secrets.token_urlsafe(32))"
```

Optional overrides (defaults are fine for most users):

```
OAUTH_CLIENT_ID=claude-mcp-client   # default
TRADIER_USE_SANDBOX=false           # true routes to sandbox.tradier.com
TRADIER_SANDBOX_TOKEN=              # required when USE_SANDBOX=true
RATE_LIMIT_PER_MINUTE=100           # safety margin under Tradier's 60-120 cap
MAX_CONCURRENT_REQUESTS=4
LOG_LEVEL=INFO
```

After saving, Railway redeploys automatically.

### Step 3: Verify the deployment

Once Railway shows the deployment as **Active**:

```bash
curl -i https://<your-railway-app>.up.railway.app/health
```

Expect HTTP 200 with a JSON body containing `version: 3.0.0` and a
`features` array that includes `Tradier data provider`.

Optional: check that env vars loaded correctly without exposing secrets:

```bash
curl -s https://<your-railway-app>.up.railway.app/debug/config
```

Returns booleans for each required variable (`tradier_api_token_set: true`,
etc.) plus the resolved `tradier_base_url` and `server_url`.

## Connect to Claude

In any Claude client (claude.ai web, Claude Desktop, mobile):

1. Open **Settings** -> **Connectors** (or **Integrations**)
2. **Add custom connector**
3. Enter:
   - **Name:** `STRAT Stock Scanner`
   - **URL:** `https://<your-railway-app>.up.railway.app/sse`
4. Save. The OAuth flow will redirect you through `/authorize` and
   `/token`, then the connector status flips to **Connected**.

Test from a Claude chat:

```
Get a stock quote for SPY.
```

A successful response confirms the OAuth flow + SSE transport + Tradier
data path are all wired correctly.

## Common Operational Issues

**`SERVER_URL` mismatch:** OAuth discovery at
`/.well-known/oauth-protected-resource` returns the value of
`settings.SERVER_URL`. If that value points at a stale or wrong domain,
MCP clients get redirected to that wrong domain for OAuth and fail to
connect. Symptoms: claude.ai shows the connector as connecting briefly
then errors; `/health` is still reachable but tool calls return "MCP
server not connected." Fix: update `SERVER_URL` in Railway to match the
domain users hit.

**Tradier returns plain-text 401 on auth failure:** Production Tradier
returns `Content-Type: plain/text` with body `"Invalid Access Token"` for
invalid bearer tokens, not the JSON `{"fault": ...}` shape documented in
some Tradier developer pages. The `_request` non-200 branch handles this
cleanly; the log line `tradier non-200 ... status_code=401 ... body=Invalid
Access Token` is the signal. Fix: verify `TRADIER_API_TOKEN` is set to a
valid production token.

**Hourly bar alignment:** `analyze_strat_patterns ... timeframe=1Hour`
aggregates 15min Tradier bars into 1-hour buckets aligned to the 9:30 ET
session open (not UTC midnight). This matches how TradingView presents
hourly bars. Native 1H interval is not supported by Tradier's timesales
endpoint, so aggregation is mandatory.

**Class-share symbols (BRK.B, BF.B):** Tradier uses `/` as the class-share
separator (`BRK/B`, `BF/B`). `tradier_client._to_tradier_symbol` translates
dots to slashes on outbound API calls and back to dots on inbound responses,
so callers can keep using canonical `BRK.B` notation everywhere.

## Deployment Checklist

- [ ] Created GitHub repo with current scanner files
- [ ] Created Railway service connected to the repo
- [ ] Added Tradier + OAuth env vars (token, JWT secret, OAuth client
      secret, server URL)
- [ ] Verified `/health` returns 200 with Tradier-flavored body
- [ ] Verified `/debug/config` shows all required variables set
- [ ] Added custom connector in Claude (pointed at `/sse`)
- [ ] Authenticated via the OAuth flow
- [ ] Confirmed a sample tool call returns real Tradier data
