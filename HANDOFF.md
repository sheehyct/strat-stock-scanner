# MCP Server Debugging Handoff Document

## Current Status: Connection Working, Data Retrieval Issues Remain

**Last Updated:** 2025-11-17

---

## 🎯 What's Working

✅ **MCP Server Deployment**
- Server deployed to Railway: `https://strat-stock-scanner-production.up.railway.app`
- Health endpoint responding: `/health` returns 200
- OAuth metadata configured: `/.well-known/oauth-protected-resource`

✅ **Claude Connection Established**
- Claude successfully connects to the MCP server via SSE
- OAuth 2.1 authentication flow completes
- Tools are discoverable and callable from Claude

✅ **Partial Tool Functionality**
- `get_stock_quote` tool **WORKS** - returns bid/ask data for stocks
- Other tools connect but fail during data retrieval

✅ **Environment Configuration**
- Alpaca API credentials ARE loaded in Railway (verified via `/debug/config`)
- Using credentials: `PKOQ...` (SMALL account from paper trading)
- All required environment variables present

---

## ❌ Current Problem

**Symptom:** Claude can call tools but gets errors or "No data available" responses

**Example Errors from Claude:**
1. "No data available for AAPL"
2. "Error occurred during tool execution"
3. Generic errors without detailed messages

**Railway Logs Show:**
- ✅ SSE connections establish: `GET /sse HTTP/1.1" 200 OK`
- ⚠️ Messages endpoint may still have issues: `POST /messages?session_id=... HTTP/1.1" 307 Temporary Redirect` (as of last check)
- ❌ No Alpaca API error logs appearing (despite error logging code added)

---

## 🔧 What's Been Tried

### 1. **MCP SDK Implementation** ✅ FIXED
- **Initial Problem:** Used wrong library (`fastapi-mcp` instead of official `mcp`)
- **Solution:** Rewrote server.py with official MCP Python SDK (`mcp>=1.2.1`)
- **Files Changed:** `server.py`, `requirements.txt`, created `tools.py`
- **Status:** Working - Claude connects successfully

### 2. **SSE Transport Configuration** ✅ FIXED
- **Initial Problem:** Wrong endpoint pattern (single endpoint vs two-endpoint requirement)
- **Solution:** Implemented proper two-endpoint SSE pattern:
  - `GET /sse` - SSE stream endpoint
  - `POST /messages` - Client message endpoint
- **Files Changed:** `server.py`
- **Status:** Working - connections establish

### 3. **Authentication with SSE** ✅ FIXED
- **Initial Problem:** FastAPI `Depends()` doesn't work with raw ASGI/SSE connections
- **Solution:** Manual JWT validation in endpoints by extracting Authorization header
- **Added:** `validate_token_string()` helper function
- **Files Changed:** `server.py`
- **Status:** Working - auth succeeds

### 4. **ASGI Double Response Error** ⚠️ PARTIALLY FIXED
- **Initial Problem:** `RuntimeError: Unexpected ASGI message 'http.response.start' sent, after response already completed`
- **Cause:** SSE transport sends its own response, FastAPI also tries to send one
- **Solutions Attempted:**
  1. Remove `return` statement - Still failed
  2. Create ASGI middleware wrapper - Still failed
  3. Use `app.mount()` - Caused 307 redirects
  4. Use `Route` with endpoint function - **CURRENT IMPLEMENTATION**
- **Files Changed:** `server.py` (multiple iterations)
- **Status:** May still have issues - need to verify in Railway logs

### 5. **307 Redirect on /messages** ⚠️ ONGOING ISSUE
- **Problem:** `/messages` endpoint returns 307 Temporary Redirect
- **Cause:** FastAPI/Starlette routing adds trailing slash redirects
- **Solutions Attempted:**
  1. `app.mount()` - Still redirected
  2. `app.routes.append(Mount(...))` - Still redirected
  3. `Route` with endpoint function - **CURRENT**, may still redirect
- **Latest Code:** `server.py:273-278`
- **Status:** Needs verification - last logs still showed 307

### 6. **Error Logging Added** ✅ IMPLEMENTED
- **Added:** Error logging in `alpaca_client.py` for debugging:
  ```python
  print(f"❌ Alpaca bars API error: {response.status_code} - {response.text[:200]}")
  ```
- **Added:** `/debug/config` endpoint to verify environment variables
- **Files Changed:** `alpaca_client.py`, `server.py`
- **Status:** Implemented but no error logs appearing (suspicious)

---

## 🔍 Key Files & Architecture

### Core Server Files
- **`server.py`** - Main MCP server with SSE endpoints, OAuth, and tool registration
- **`tools.py`** - Wrapper exports for MCP tool functions
- **`mcp_tools.py`** - Actual tool implementations (get_quote, analyze_strat, scan_sector, etc.)
- **`alpaca_client.py`** - Alpaca API wrapper with rate limiting
- **`auth_server.py`** - OAuth 2.1 authorization server implementation
- **`auth_middleware.py`** - JWT token validation
- **`config.py`** - Environment variable configuration (Pydantic Settings)
- **`strat_detector.py`** - STRAT pattern detection logic
- **`rate_limiter.py`** - Rate limiting for Alpaca API (180 req/min)

### Critical Endpoints
```
GET  /sse                           - SSE stream for MCP (requires auth)
POST /messages?session_id=<uuid>    - Client messages (requires auth)
GET  /.well-known/oauth-protected-resource - OAuth metadata
POST /authorize                     - OAuth authorization
POST /token                         - OAuth token exchange
GET  /health                        - Health check
GET  /debug/config                  - Debug environment vars (shows API key prefix)
```

### MCP Tools Registered
1. `get_stock_quote(ticker)` - ✅ Working
2. `analyze_strat_patterns(ticker, timeframe, days_back)` - ❌ Failing
3. `scan_sector_for_strat(sector, top_n, pattern_filter)` - ❌ Not tested
4. `scan_etf_holdings_strat(etf, top_n)` - ❌ Not tested
5. `get_multiple_quotes(tickers)` - ❌ Not tested

---

## 🧪 Diagnostic Commands

### Check Server Status
```bash
curl https://strat-stock-scanner-production.up.railway.app/health
```

### Verify Credentials Loaded
```bash
curl https://strat-stock-scanner-production.up.railway.app/debug/config
```
**Expected Output:**
```json
{
  "alpaca_api_key_set": true,
  "alpaca_api_secret_set": true,
  "alpaca_base_url": "https://data.alpaca.markets/v2",
  "jwt_secret_set": true,
  "server_url": "https://strat-stock-scanner-production.up.railway.app",
  "api_key_prefix": "PKOQ..."
}
```

### Test Alpaca API Directly
```bash
curl "https://data.alpaca.markets/v2/stocks/AAPL/bars?start=2025-11-01&end=2025-11-15&timeframe=1Day&feed=iex&limit=10" \
  -H "APCA-API-KEY-ID: PKOQWHH32GDJ44CDUMPYEHGVEW" \
  -H "APCA-API-SECRET-KEY: <secret>"
```

### Check Railway Logs
```bash
# In Railway dashboard:
# Project → Deployments → View logs
# Look for:
# - "❌ Alpaca bars API error: XXX"
# - "307 Temporary Redirect" on /messages
# - ASGI errors
```

---

## 🐛 Remaining Issues & Next Steps

### Issue 1: 307 Redirect on /messages Still Occurring
**Problem:** Last logs showed `POST /messages?session_id=...` returning 307

**Possible Solutions:**
1. **Option A: Use raw ASGI app mount at root level**
   ```python
   # In server.py, before app creation
   from starlette.applications import Starlette
   from starlette.routing import Route, Mount

   # Create separate ASGI app for /messages
   messages_app = Starlette(routes=[
       Route("/", endpoint=AuthenticatedMessagesApp(sse_transport.handle_post_message), methods=["POST"])
   ])

   # Mount it
   app.mount("/messages", messages_app)
   ```

2. **Option B: Use APIRouter instead**
   ```python
   from fastapi import APIRouter

   messages_router = APIRouter()

   @messages_router.api_route("/messages", methods=["POST"])
   async def handle_messages(request: Request):
       # Auth and delegate to transport
       ...
   ```

3. **Option C: Check if trailing slash is the issue**
   - Try connecting to `/messages/` (with slash) in the SSE transport
   - Change `SseServerTransport("/messages")` to `SseServerTransport("/messages/")`
   - Update client expectations

### Issue 2: No Error Logs from Alpaca Client
**Problem:** Despite adding error logging, no `❌ Alpaca` messages appear in logs

**Diagnosis Needed:**
1. **Check if alpaca_client methods are even being called**
   - Add `print(f"🔍 Fetching bars for {ticker}")` at start of `get_bars_recent()`
   - Check Railway logs for these debug messages

2. **Check for silent exceptions**
   - Wrap tool functions in try/except with explicit logging
   - In `mcp_tools.py`, add error handling:
     ```python
     async def analyze_strat_patterns(ticker, timeframe, days_back):
         try:
             print(f"🔍 Starting STRAT analysis for {ticker}")
             bars = await alpaca.get_bars_recent(...)
             print(f"✅ Got {len(bars)} bars")
             ...
         except Exception as e:
             print(f"❌ STRAT analysis failed: {type(e).__name__}: {str(e)}")
             import traceback
             traceback.print_exc()
             raise
     ```

3. **Verify error handling in rate_limiter.py**
   - Check if rate limiter is swallowing errors
   - Review `alpaca_limiter.make_request()` implementation

### Issue 3: Verify Alpaca Data API Access
**Problem:** Credentials loaded but data not returning

**Things to Check:**
1. **Account type vs API endpoint mismatch**
   - Currently using: `https://data.alpaca.markets/v2` (data API)
   - Credentials are from: Paper trading accounts
   - **CRITICAL:** Paper trading credentials should still work for market data API
   - But verify in Alpaca dashboard: Do these keys have data API access?

2. **Test with IEX feed explicitly**
   - In `mcp_tools.py` line 52, change:
     ```python
     bars = await alpaca.get_bars_recent(ticker, days_back=days_back, timeframe=timeframe, feed="iex")
     ```
   - IEX is free tier, SIP requires paid subscription
   - Current default is "sip" which may be failing

3. **Check timeframe format**
   - Alpaca expects specific timeframe formats
   - Verify "1Day" vs "1D" vs "1day"
   - Check Alpaca API docs for correct format

### Issue 4: ASGI Errors May Still Be Occurring
**Problem:** Complex ASGI middleware may have edge cases

**Simplest Solution:**
- **Remove authentication from /messages entirely for testing**
  ```python
  # Temporarily disable auth to isolate the issue
  app.routes.append(
      Route("/messages",
            endpoint=lambda request: sse_transport.handle_post_message(request.scope, request.receive, request._send),
            methods=["POST"])
  )
  ```
- If this works, the issue is auth middleware + ASGI interaction
- Then implement auth at a different layer (ASGI middleware, not route-level)

---

## 🔑 Railway Environment Variables

**Verify these are set in Railway dashboard:**

```bash
# Alpaca Credentials
ALPACA_API_KEY=PKOQWHH32GDJ44CDUMPYEHGVEW
ALPACA_API_SECRET=FMJuXfFaaPeuZzy6tTMoFoHieW5fBYWzyAKQHUJw2DDN
ALPACA_BASE_URL=https://data.alpaca.markets/v2

# OAuth Secrets
JWT_SECRET_KEY=<generated-secret>
OAUTH_CLIENT_ID=claude-mcp-client
OAUTH_CLIENT_SECRET=<generated-secret>

# Server Config
SERVER_URL=https://strat-stock-scanner-production.up.railway.app
PORT=8080
DEBUG=false
```

**Note:** Variable names MUST match `config.py` exactly:
- `ALPACA_API_SECRET` (NOT `ALPACA_SECRET_KEY`)
- Check `.env` file has different naming - Railway must use correct names

---

## 📝 Recommended Debugging Strategy

### Phase 1: Simplify & Isolate (Highest Priority)
1. **Remove authentication from /messages temporarily**
   - Goal: Determine if issue is auth middleware or transport
   - If works without auth, problem is auth wrapper
   - If still fails, problem is transport or Alpaca API

2. **Add extensive logging**
   - Tool entry points
   - Alpaca client method calls
   - Rate limiter
   - Every step of data flow

3. **Test with curl directly**
   - Bypass Claude entirely
   - Call tools via MCP protocol with curl
   - Isolate whether issue is Claude-side or server-side

### Phase 2: Fix Transport Issues
1. **Resolve 307 redirects completely**
   - May need to restructure routing
   - Consider using plain Starlette instead of FastAPI for MCP endpoints

2. **Fix ASGI double response**
   - Ensure clean delegation to transport
   - No wrapper functions trying to return

### Phase 3: Fix Data Retrieval
1. **Verify Alpaca API access**
   - Test credentials outside of MCP server
   - Check data feed permissions (IEX vs SIP)

2. **Fix error propagation**
   - Ensure errors bubble up to logs
   - Return detailed error messages to Claude

### Phase 4: Production Hardening
1. **Proper error handling in all tools**
2. **Rate limiting verification**
3. **Token refresh handling**
4. **Logging cleanup (remove excessive debug logs)**

---

## 🚀 Quick Wins to Try First

1. **Change default feed from "sip" to "iex"**
   ```python
   # In mcp_tools.py:52
   bars = await alpaca.get_bars_recent(ticker, days_back=days_back, timeframe=timeframe, feed="iex")
   ```

2. **Add debug logging at tool entry**
   ```python
   # In mcp_tools.py
   async def analyze_strat_patterns(ticker, timeframe="1Day", days_back=10):
       print(f"🔍 [TOOL] analyze_strat_patterns called: ticker={ticker}, timeframe={timeframe}, days_back={days_back}")
       try:
           # ... existing code
       except Exception as e:
           print(f"❌ [TOOL] analyze_strat_patterns error: {e}")
           import traceback
           traceback.print_exc()
           raise
   ```

3. **Test /messages endpoint directly with curl**
   ```bash
   # Get OAuth token first
   TOKEN=$(curl -X POST https://strat-stock-scanner-production.up.railway.app/token \
     -d "grant_type=client_credentials&client_id=claude-mcp-client&client_secret=<secret>" \
     | jq -r .access_token)

   # Test messages endpoint
   curl -X POST "https://strat-stock-scanner-production.up.railway.app/messages?session_id=test123" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}' \
     -v
   ```

---

## 📚 Reference Links

- **MCP Specification:** https://modelcontextprotocol.io/specification
- **MCP Python SDK:** https://github.com/modelcontextprotocol/python-sdk
- **SSE Transport Example:** https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/sse.py
- **Alpaca Data API Docs:** https://alpaca.markets/docs/api-references/market-data-api/
- **FastAPI ASGI:** https://fastapi.tiangolo.com/advanced/custom-request-and-route/
- **Starlette Routing:** https://www.starlette.io/routing/

---

## 💡 Alternative Approaches if All Else Fails

### Option 1: Use Cloudflare Workers for MCP
- Cloudflare has native MCP support
- Simpler deployment model
- Better SSE handling

### Option 2: Separate Services
- Deploy OAuth server separately
- Deploy MCP server without auth (behind API gateway)
- Use Railway's internal networking

### Option 3: Use fastmcp Library
- Simpler abstraction over official SDK
- Handles SSE transport automatically
- May avoid current routing issues
- Trade-off: Less control, different patterns

---

## ✅ Success Criteria

**Minimum Viable:**
- [ ] Claude can call `analyze_strat_patterns` without errors
- [ ] Server returns actual STRAT data or clear error messages
- [ ] No 307 redirects in Railway logs
- [ ] No ASGI errors in Railway logs

**Fully Working:**
- [ ] All 5 MCP tools work correctly
- [ ] Error messages are informative
- [ ] Rate limiting functions properly
- [ ] OAuth token refresh works
- [ ] Performance is acceptable (< 2s response time)

---

## 🎯 Most Likely Root Cause (Best Guess)

Based on the progression of issues:

1. **Primary Suspect:** `/messages` endpoint routing is still broken
   - 307 redirects prevent proper message delivery
   - MCP protocol breaks when messages don't reach server
   - Tools appear to "work" but never complete

2. **Secondary Suspect:** Alpaca API feed mismatch
   - Using "sip" feed (paid) with paper account
   - Should use "iex" feed (free) for testing
   - No errors logged because request never reaches Alpaca

3. **Tertiary Suspect:** ASGI middleware eating exceptions
   - Error handling wrapper may be catching and suppressing errors
   - Prevents error logs from appearing
   - Claude sees generic "tool failed" instead of actual error

**Recommended Fix Order:**
1. Fix `/messages` 307 redirect (highest impact)
2. Add extensive logging to confirm tool execution flow
3. Switch to IEX feed for data fetching
4. Simplify ASGI middleware if still having issues

---

## 📞 Handoff Complete

This document contains everything needed to continue debugging. Start with the "Quick Wins" section, then follow the debugging strategy in order.

**Last Known State:**
- Commit: `4956438` - "fix: use Route with endpoint function to avoid redirects"
- Deployment: Live on Railway
- Claude Connection: Established
- Tool Execution: Failing at data retrieval stage

**Files to Focus On:**
1. `server.py:273-278` - /messages endpoint routing
2. `mcp_tools.py:31-86` - analyze_strat_patterns implementation
3. `alpaca_client.py:101-129` - get_bars_recent method

Good luck! 🚀
