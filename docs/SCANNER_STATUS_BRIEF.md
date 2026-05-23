# Scanner Status Brief

One-page snapshot of the scanner's deployment state. Update on every
session end via `/session-end`. This is Tier-2 reading; check it whenever
you need to know "is it up, what's it talking to, is it broken."

---

## Deployment

| Field | Value |
|-------|-------|
| MCP Server URL | `https://strat-stock-scanner-production.up.railway.app` |
| Platform | Railway |
| Health Endpoint | `/health` |
| OAuth Metadata | `/.well-known/oauth-protected-resource` |
| SSE Stream | `GET /sse` |
| Message Endpoint | `POST /messages` |
| Auto-Deploy | Yes - `git push origin main` triggers Railway redeploy |

## Data Provider

| Field | Value |
|-------|-------|
| Current Provider | Alpaca SIP feed (legacy) |
| Migration Target | Tradier (in progress on separate feature branch) |
| Timezone | `America/New_York` (mandatory on all fetches) |
| Holiday Filter | Not yet wired - add `pandas_market_calendars` when needed |

## Last Known Healthy Date

`2025-11-17` per `../HANDOFF.md`. Status since then is uncertain; the scanner
has been dormant pending the Tradier migration.

## Current Blockers

1. Alpaca credentials may have rotated since November 2025 - verify before
   declaring the scanner "broken."
2. Tradier migration on separate branch must land before the scanner can
   resume normal use.
3. MCP-over-SSE transport had a 307 redirect issue on `/messages` as of
   the last debugging session; verify it has not regressed.

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

- 180 requests/minute soft cap (under Alpaca's 200/min limit)
- Max 3 concurrent in-flight requests
- Exponential backoff on 429

## How to Verify Health Quickly

```bash
curl -i https://strat-stock-scanner-production.up.railway.app/health
```

Expect HTTP 200. If anything else, check Railway logs:

```bash
railway logs
```

## Last Updated

`2026-05-21` - workflow scaffolding bootstrap. Update this section when the
brief changes.
