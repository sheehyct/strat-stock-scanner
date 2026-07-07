# STRAT Stock Scanner - Development Rules

> Scanner-specific rules. Universal safety rules inherited from
> `C:\Strat_Trading_Bot\CLAUDE.md` (the spine context file).

## What This Project Is

A small MCP server (~3000 LOC) deployed to Railway, used by the user's mobile
Claude app for **conversational** TFC scanning during market discussions.

**This is NOT a trading system.** It does not place orders, manage positions,
or execute strategies. It exposes STRAT pattern detection and Timeframe
Continuity (TFC) scoring as MCP tools so the user can ask "what's SPY's TFC
look like right now?" from a phone and get a real answer.

Sister project: `C:\Strat_Trading_Bot\vectorbt-workspace` (ATLAS) - the
algorithmic backtesting and live-trading platform. ATLAS is the source of
methodology truth; the scanner is a read-only consumer.

## Session Start

1. Read `docs/HANDOFF.md` (current state and recent sessions)
2. Read `.session_startup_prompt.md` (current mission)
3. Verify tests pass: `uv run pytest tests/ -q`
4. Verify MCP transport health: see `docs/SCANNER_STATUS_BRIEF.md`

## MANDATORY Skills (ZERO TOLERANCE)

**MUST invoke this skill before writing related code. No exceptions.**

| Skill | Invoke When |
|-------|-------------|
| `strat-methodology` | ANY STRAT pattern detection, bar classification, timeframe analysis, TFC scoring change |

The other ATLAS-specific skills (thetadata-api, backtesting-validation,
dashboard-design) do NOT apply here. The scanner does not hit ThetaData,
does not backtest, and has no dashboard UI.

## Communication Standards

- NO emojis or unicode characters (Windows terminal compatibility)
- NO AI attribution in commits or docs
- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Professional tone, plain ASCII only
- All timestamps: timezone-aware (`tz='America/New_York'` for market data)

## Brutal Honesty Policy

- If you don't know, say "I don't know"
- If guessing, say "I'm guessing"
- If wrong approach, say "This is wrong because..."
- If simpler way exists, suggest it
- If task adds complexity without value, say so

## STRAT Bar Classification (MANDATORY)

Every directional bar MUST be classified as 2U (bullish) or 2D (bearish).
Never use just "2".

| Correct | Incorrect |
|---------|-----------|
| 2D-2U | 2-2 |
| 3-2U, 3-2D | 3-2 |
| 3-2U-2U, 3-2D-2D | 3-2-2 |
| 2U-1-2U, 2D-1-2D | 2-1-2 |
| 3-1-2U, 3-1-2D | 3-1-2 (OK - only exit bar needs direction) |

Bar types: 1=inside, 2U=up, 2D=down, 3=outside

## STRAT Entry Timing (ZERO TOLERANCE)

**Entry happens ON THE BREAK, not at bar close.** This is the most common
implementation error and the source of the largest backtest-vs-live drift
in the parent ATLAS project.

| Concept | Rule |
|---------|------|
| Entry is LIVE | When price breaks trigger level, enter IMMEDIATELY |
| Forming bar classification | Only "1" if it stays INSIDE prior range - NOT automatic |
| Pre/post market gaps | Bar can OPEN as 2U/2D due to overnight action |
| Pattern completion | Happens the MOMENT price breaks, not at bar close |

**Scanner-specific implication:**

- The scanner reports patterns based on the most-recent CLOSED bar plus the
  in-flight FORMING bar.
- The forming bar is NOT automatically a "1" - reclassify on every poll.
- If the user asks "did the 3-1-2 just complete?" the answer is yes the
  moment price prints through the trigger, not at the next bar close.

See `strat-methodology` skill Section 1 (critical invariants) and Section 3.1 (detection rules): entry fires the instant price breaks the trigger, intrabar.

## Data Sources

| Source | Use Case |
|--------|----------|
| Alpaca (SIP feed) | Primary - all equities and ETFs |

**ALWAYS:** `tz='America/New_York'` on all data fetches.

**NEVER:** Synthetic data, mock OHLCV generators, yfinance for equities.

Tradier migration is in progress on a separate feature branch; once
shipped, Tradier replaces Alpaca as the primary data source. Until then,
treat the scanner as broken in any environment where Alpaca credentials
are unavailable. See `docs/HANDOFF.md` for migration status.

## Market Data Rules

- Filter weekends: `data.index.dayofweek < 5`
- Verify no Saturday/Sunday bars before any analysis
- US holiday filtering: use `pandas_market_calendars` if/when added

## MCP Server Health and Transport Integrity

The scanner is reached via MCP-over-SSE from the mobile Claude client. Two
classes of bug exist:

1. **Transport bugs** - SSE handshake, OAuth flow, 307 redirects on
   `/messages`, session-id mismatches. Symptom: tools listed but every call
   errors. See HANDOFF.md history for prior fixes.
2. **Data-path bugs** - tool registered, transport healthy, but the
   underlying data provider returns empty or wrong-timezone data.

Before changing transport code, verify the change against the official MCP
Python SDK. Before changing the data path, verify timezone handling.

## Real-Time Data Freshness

The mobile-app use case is "what is happening RIGHT NOW," so:

- Intraday timeframes (15m, 60m) MUST include the forming bar
- 1d and higher MAY use last closed bar if the day hasn't closed
- Quote endpoints SHOULD return last trade timestamp so the client can
  show "as of 14:32 ET" to the user
- If a fetch errors, fail loudly - do NOT return stale cached data without
  flagging it as stale

## Railway Deployment Context

- Server URL: `https://strat-stock-scanner-production.up.railway.app`
- Deploy: `git push origin main` triggers Railway redeploy
- Env vars are managed in the Railway dashboard, NOT in `.env` files in
  the repo
- Health endpoint: `/health` (returns 200 when up)
- OAuth metadata: `/.well-known/oauth-protected-resource`
- Logs: Railway dashboard or `railway logs`

Never deploy code with failing local tests. Run `uv run pytest tests/ -x -q`
locally before any push to `main`.

## Security Rules

- NEVER commit `.env` files (use `.env.example` for templates)
- NEVER hardcode API keys, secrets, or VPS IP addresses in source or docs
- The GitHub repo is PUBLIC - assume any committed string is world-readable
- Flask/FastAPI servers default to `127.0.0.1` for any local-dev binding;
  Railway sets the production bind via env var
- NEVER pass `debug=True` to Flask/FastAPI in production
- OAuth tokens: short TTL (<= 1h), rotate JWT signing key on credential
  leak suspicion

## Account Constraints (inherited)

Schwab Level 1 Options (cash account):
- CAN: Long stock, long calls/puts, cash-secured puts
- CANNOT: Short stock, naked options, spreads

The scanner itself does not place trades, so this is only relevant if the
user is using the scanner's output to inform manual orders.

## DO NOT

- Skip HANDOFF.md at session start
- Skip the `strat-methodology` skill when touching STRAT detection code
- Use yfinance for equity data
- Generate synthetic or mock OHLCV
- Use unclassified "2" bars (must be 2U or 2D)
- Wait for bar close to report a STRAT entry as triggered
- Commit `.env`, credentials, or VPS IP addresses
- Pass `debug=True` to production servers
- Use `cd <path> && git` compound commands (use `git -C <path>` instead)

## Hook Infrastructure

Hooks wire to the parent `.claude/hooks/` directory:

| Hook | Event | Script |
|------|-------|--------|
| Trading safety guard | PreToolUse | `C:/Strat_Trading_Bot/.claude/hooks/safety_guard.py --scope trading` |
| Ruff auto-lint | PostToolUse | `C:/Strat_Trading_Bot/.claude/hooks/post_edit_lint.py` |

Do NOT modify hook scripts in this repo - they live in the parent
directory and are shared across all projects.

## Key Commands

```bash
# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_auth.py -v

# Smoke test (quick)
uv run pytest tests/ -x -q

# Local server
uv run python server.py
```

Git commands: always use `git -C <path>` instead of `cd <path> && git`
to avoid compound-command approval prompts.

## Reference

| Tier | File | When to Read |
|------|------|--------------|
| 1 | `docs/HANDOFF.md`, `CLAUDE.md` | Every session |
| 2 | `docs/SCANNER_STATUS_BRIEF.md` | When verifying deployment health |
| 3 | `docs/INDEX.md` | When looking for any other doc |
