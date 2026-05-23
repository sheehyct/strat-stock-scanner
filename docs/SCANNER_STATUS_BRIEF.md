# Scanner Status Brief

One-page snapshot of the scanner's deployment state. Update on every
session end via `/session-end`. This is Tier-2 reading; check it whenever
you need to know "is it up, what's it talking to, is it broken."

---

## Deployment

| Field | Value |
|-------|-------|
| MCP Server URL | `https://strat-stock-scanner-atlas-monitoring.up.railway.app` |
| Platform | Railway |
| Health Endpoint | `/health` |
| OAuth Metadata | `/.well-known/oauth-protected-resource` |
| SSE Stream | `GET /sse` |
| Message Endpoint | `POST /messages` |
| Auto-Deploy | Yes - `git push origin main` triggers Railway redeploy |

Note: the older URL `https://strat-stock-scanner-production.up.railway.app`
is a Railway fallback corpse (no container backing it); requests there
return HTTP 502 with `X-Railway-Fallback: true`. Update any bookmarks /
integrations to the atlas-monitoring URL.

## Data Provider

| Field | Value |
|-------|-------|
| Current Provider | Tradier Market Data REST API |
| Auth | Single bearer token (`TRADIER_API_TOKEN`) |
| Endpoints used | `/markets/quotes`, `/markets/history`, `/markets/timesales`, `/markets/clock` |
| Timezone | `America/New_York` (mandatory on all fetches) |
| Holiday Filter | Not yet wired - add `pandas_market_calendars` when needed |
| Migration history | Migrated from Alpaca SIP feed on 2026-05-23 (PR #4) |

## Last Known Healthy Date

`2026-05-23` - fully validated end-to-end with live Tradier production
data. Step 7 checklist completed: real quote, batch quote, class-share
symbol (BRK.B), daily STRAT analysis (64 bars), hourly STRAT analysis
(open-aligned aggregator), ETF holdings scan (15 stocks including
BRK.B at position #7), rate limiting clean (15 consecutive ticker
fetches, zero 429s). See `../HANDOFF.md` top entry for the full
validation results.

## Current Blockers

None. Scanner is operational. Follow-up PRs queued for future sessions:

1. **OAuth client validation** (security; bounded risk for personal
   use) - `auth_server.py:109-291` accepts arbitrary `client_id` /
   `client_secret` / `redirect_uri` without validation. Tighten in a
   focused PR.
2. **Typed provider errors** - distinguish "symbol unknown" from
   "auth/rate-limit failure" at tool-response level.
3. **Architecture/perf** - process-lifetime httpx.AsyncClient;
   rate-limiter releases semaphore before retry backoff.

## Tools Exposed via MCP

(Reference - update if `mcp_tools.py` adds/removes tools.)

| Tool | Purpose |
|------|---------|
| `get_stock_quote` | Real-time bid/ask snapshot |
| `get_multiple_quotes` | Bulk quote lookup |
| `analyze_strat_patterns` | Deep STRAT analysis on a single symbol |
| `analyze_tfc` | Multi-timeframe TFC scoring for a single symbol |
| `scan_sector_for_strat` | Scan a sector universe for existing patterns |
| `scan_etf_holdings_strat` | Scan ETF holdings (SPY, QQQ, IWM, etc.) |
| `scan_for_tfc_alignment` | Scan a universe for TFC-aligned setups |

## Authentication

- OAuth 2.1 with PKCE
- JWT-based session tokens
- Mobile Claude client is the primary consumer; Claude Desktop also supported

## Rate Limiting

- 100 requests/minute soft cap (Tradier production caps endpoints at
  60-120/min depending on endpoint; we cap conservatively below the
  lower bound for safety margin)
- Max 4 concurrent in-flight requests (`MAX_CONCURRENT_REQUESTS`)
- Exponential backoff on 429 (up to 2 retries with 1s and 2s waits)

## How to Verify Health Quickly

```bash
curl -i https://strat-stock-scanner-atlas-monitoring.up.railway.app/health
```

Expect HTTP 200 with `version: 3.0.0` and a `features` array that lists
`Tradier data provider (consolidated real-time tape)`. If anything else,
check Railway Deploy Logs:

```bash
railway logs
```

## Last Updated

`2026-05-23` - Tradier migration shipped (PR #3 + PR #4 merged to main).
Update this section when the brief changes.
