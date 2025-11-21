# Debugging Session Summary - 2025-11-17

## 🎯 What We Accomplished

### 1. **Added Comprehensive Debug Logging** ✅
- **mcp_tools.py:47-68** - Added entry/exit logging for `analyze_strat_patterns()`
- **alpaca_client.py:85-119** - Added detailed API request/response logging
- **server.py:147-182** - Added tool call logging with arguments and errors
- **server.py:214-237** - Added SSE connection logging

### 2. **Fixed /messages Endpoint Response Handling** ✅
- **server.py:274-286** - Added logging and clarified that ASGI app handles its own response
- Removed confusing return statement that could cause double-response errors

### 3. **Fixed config.py to Ignore Extra .env Fields** ✅
- **config.py:38** - Added `extra = "ignore"` to allow legacy .env variables

### 4. **Updated .env File** ✅
- Added `ALPACA_API_SECRET` (duplicate of `ALPACA_SECRET_KEY` for compatibility)
- Changed `ALPACA_BASE_URL` to correct data API: `https://data.alpaca.markets/v2`
- Added OAuth and server configuration variables

### 5. **Created Test Script** ✅
- **test_alpaca_direct.py** - Direct API testing tool (no MCP involved)
- Tests quote, bars (SIP), bars (IEX), and account info
- Fixed Unicode emoji issues for Windows console

---

## ❌ Issue Discovered: Config Not Loading Correct BASE_URL

### The Problem
Despite setting `ALPACA_BASE_URL=https://data.alpaca.markets/v2` in `.env`, the config is loading `https://paper-api.alpaca.markets`.

### Test Results
```
Base URL: https://paper-api.alpaca.markets  ← WRONG!
API Key: PKOQWHH32G...

quote_iex: [FAIL] - 404 endpoint not found
bars_sip: [FAIL] - 404 endpoint not found
bars_iex: [FAIL] - 404 endpoint not found
account: [PASS] - Trading API works fine
```

### Why This Matters
- The trading API (`https://paper-api.alpaca.markets/v2`) is for orders, positions, account info
- The **data API** (`https://data.alpaca.markets/v2`) is for quotes, bars, market data
- We're trying to hit data endpoints on the trading API URL = 404 errors

### Root Cause (To Investigate)
1. **Python module caching** - `config.py` might be cached with old values
2. **Another .env file** - Could be loading from a different location
3. **Pydantic Settings priority** - Environment variables might override .env file

---

## 🔧 Next Steps (When You Resume)

### Step 1: Fix the BASE_URL Loading Issue

**Option A: Clear Python cache**
```bash
rm -rf __pycache__
python -c "from config import settings; print(f'URL: {settings.ALPACA_BASE_URL}')"
```

**Option B: Check for environment variables**
```bash
# Windows
echo %ALPACA_BASE_URL%

# If set, unset it
set ALPACA_BASE_URL=
```

**Option C: Verify .env is being read**
```python
# Add to config.py temporarily
class Settings(BaseSettings):
    # ... existing fields ...

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print(f"[CONFIG DEBUG] Loaded ALPACA_BASE_URL: {self.ALPACA_BASE_URL}")
        print(f"[CONFIG DEBUG] Loaded from .env file: {self.Config.env_file}")
```

**Option D: Hardcode it temporarily**
```python
# In config.py, change:
ALPACA_BASE_URL: str = "https://data.alpaca.markets/v2"  # Default
# To:
ALPACA_BASE_URL: str = Field(default="https://data.alpaca.markets/v2")
```

### Step 2: Run Local Test Again
```bash
python test_alpaca_direct.py
```

**Expected Output:**
```
quote_iex: [PASS]
bars_sip: [PASS]  ← This confirms your paid tier
bars_iex: [PASS]
account: [PASS]
```

### Step 3: Commit Changes
```bash
git add .
git commit -m "fix: add comprehensive debug logging and fix /messages endpoint

- Add debug logging at tool entry, Alpaca API, and MCP server layers
- Fix /messages endpoint response handling to prevent double-response errors
- Update config.py to ignore extra .env fields
- Add test script for direct Alpaca API verification"
```

### Step 4: Deploy to Railway
```bash
git push origin main
```

**IMPORTANT: Verify Railway Environment Variables**
In Railway dashboard, ensure these are set:
```
ALPACA_API_KEY=PKOQWHH32GDJ44CDUMPYEHGVEW
ALPACA_API_SECRET=FMJuXfFaaPeuZzy6tTMoFoHieW5fBYWzyAKQHUJw2DDN
ALPACA_BASE_URL=https://data.alpaca.markets/v2  ← CRITICAL!
JWT_SECRET_KEY=<your-production-secret>
OAUTH_CLIENT_ID=claude-mcp-client
OAUTH_CLIENT_SECRET=<your-production-secret>
SERVER_URL=https://strat-stock-scanner-production.up.railway.app
PORT=8080
DEBUG=false
```

### Step 5: Watch Railway Logs
After deployment, watch for debug messages:
```
🔧 [TOOL CALL] Tool: analyze_strat_patterns
📋 [TOOL CALL] Arguments: {'ticker': 'AAPL', 'timeframe': '1Day', 'days_back': 10}
🔍 [TOOL ENTRY] analyze_strat_patterns: ticker=AAPL, timeframe=1Day, days_back=10
📊 [API CALL] Fetching bars for AAPL...
🔍 [ALPACA] get_bars_recent: ticker=AAPL, days_back=10, timeframe=1Day, feed=sip
📅 [ALPACA] Date range: 2025-11-07T... to 2025-11-17T...
🌐 [ALPACA API] GET https://data.alpaca.markets/v2/stocks/AAPL/bars
📋 [ALPACA API] Params: {start: ..., end: ..., timeframe: 1Day, feed: sip}
✅ [ALPACA API] Success: 10 bars returned
✅ [API RESPONSE] Received 10 bars for AAPL
✅ [TOOL CALL] analyze_strat_patterns completed successfully
```

### Step 6: Test with Claude
Ask Claude to:
```
Analyze STRAT patterns for AAPL over the last 10 days
```

If successful, you should see actual pattern analysis instead of "No data available".

---

## 📊 Diagnosis: What Logs Will Tell Us

### Scenario 1: Success (bars returned)
```
✅ [ALPACA API] Success: 10 bars returned
```
**Meaning:** Everything works! Your paid SIP tier is active.

### Scenario 2: 404 Error
```
❌ Alpaca bars API error: 404
📄 Response body: {"message": "endpoint not found."}
```
**Meaning:** Still using wrong BASE_URL. Check Railway env vars.

### Scenario 3: 403 Forbidden
```
❌ Alpaca bars API error: 403
📄 Response body: {"message": "forbidden"}
```
**Meaning:** Credentials don't have SIP access. Switch to `feed="iex"` in mcp_tools.py:56.

### Scenario 4: 400 Bad Request
```
❌ Alpaca bars API error: 400
📄 Response body: {"message": "invalid request"}
```
**Meaning:** Timeframe or date format issue. Check parameter formatting.

### Scenario 5: No Logs Appear
**Meaning:** Tool not being called. Check `/messages` endpoint for 307 redirects.

---

## 🎓 Key Learnings

### 1. Alpaca Has Two Separate APIs
- **Trading API** (`paper-api.alpaca.markets`) - Orders, positions, account
- **Data API** (`data.alpaca.markets`) - Quotes, bars, market data
- **They use the same credentials but different base URLs**

### 2. Why get_stock_quote Works But analyze_strat_patterns Doesn't
- `get_stock_quote` uses the correct data API URL (from alpaca_client.py)
- But `alpaca_client.py` reads from `settings.ALPACA_BASE_URL`
- If that setting is wrong, all bar requests fail

### 3. The /messages Endpoint Complexity
- MCP SSE transport needs two endpoints: `/sse` (GET) and `/messages` (POST)
- FastAPI's routing can cause 307 redirects if not handled carefully
- ASGI apps handle their own responses - don't try to return from wrapper functions

### 4. Railway vs Local Environment Variables
- Railway and local .env can use different variable names
- Added `extra = "ignore"` to config.py to handle legacy names
- Railway needs explicit variable setting in dashboard

---

## 📁 Files Modified

### Core Changes
1. **mcp_tools.py** - Debug logging in analyze_strat_patterns
2. **alpaca_client.py** - Debug logging in get_bars and get_bars_recent
3. **server.py** - Debug logging in call_tool, handle_sse, and messages_route
4. **config.py** - Added `extra = "ignore"` to Config class
5. **.env** - Updated with correct variable names and values

### New Files
6. **test_alpaca_direct.py** - Standalone API test script
7. **.env.test** - Test environment template
8. **DEBUGGING_SESSION_SUMMARY.md** - This file

---

## 🚨 Critical Action Items

### Before You Continue Development

1. **Fix the BASE_URL loading** - This is blocking all bar requests
2. **Run test_alpaca_direct.py** - Verify API access works locally
3. **Clear Python cache** - Delete `__pycache__` directories

### Before Deploying to Railway

1. **Verify Railway env vars** - Especially `ALPACA_BASE_URL`
2. **Check for typos** - `ALPACA_API_SECRET` (not `ALPACA_SECRET_KEY`)
3. **Test health endpoint** - Ensure deployment succeeded

### After Deployment

1. **Watch Railway logs** - Look for debug messages
2. **Test with Claude** - Try `analyze_strat_patterns` tool
3. **Check for 307 redirects** - Should see 200 OK on `/messages`

---

## 🔗 Quick Reference

### Railway Dashboard
- **URL:** https://railway.app
- **Project:** strat-stock-scanner
- **Live URL:** https://strat-stock-scanner-production.up.railway.app

### Test Endpoints
```bash
# Health check
curl https://strat-stock-scanner-production.up.railway.app/health

# Debug config (shows if env vars are set)
curl https://strat-stock-scanner-production.up.railway.app/debug/config
```

### Alpaca Data API Documentation
- **Bars:** https://alpaca.markets/docs/api-references/market-data-api/stock-pricing-data/historical/
- **Quotes:** https://alpaca.markets/docs/api-references/market-data-api/stock-pricing-data/realtime/
- **Feeds:** https://alpaca.markets/docs/market-data/getting-started/#real-time-data-feeds

---

## 💡 If All Else Fails

### Nuclear Option: Switch to IEX Feed
If SIP feed continues to fail, switch all tools to IEX (free tier):

**In mcp_tools.py:**
```python
# Line 56: Change from
feed="sip"
# To:
feed="iex"

# Line 144 and 221: Already using default, but verify
```

**Trade-offs:**
- ✅ Free, no subscription needed
- ✅ Should work with all account types
- ❌ Only IEX exchange data (not consolidated)
- ❌ 15-minute delay on historical data for Basic tier

---

## 📌 Session Context Preserved

When you resume, start with:
```bash
# 1. Check what BASE_URL is actually loading
python -c "from config import settings; print(settings.ALPACA_BASE_URL)"

# 2. If wrong, clear cache
rm -rf __pycache__
rm -rf .pytest_cache

# 3. Re-run test
python test_alpaca_direct.py
```

Good luck with the rest of the debugging! The changes we made should provide excellent visibility into what's happening. 🚀
