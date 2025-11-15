# Complete Alpaca MCP Server with STRAT Detection - Deployment Guide

## 🎯 What You're Deploying

MCP server with 5 core tools:
1. **get_stock_quote** - Real-time bid/ask prices
2. **analyze_strat_patterns** - Deep STRAT analysis on single stock
3. **scan_sector_for_strat** - Scan entire sector for existing STRAT patterns
4. **scan_etf_holdings_strat** - Scan ETF holdings (SPY, QQQ, etc.) for patterns
5. **get_multiple_quotes** - Bulk quote lookup

**STRAT Patterns Detected:**
- ✅ 2-1-2 Reversals (high confidence)
- ✅ 3-1-2 Continuations (high confidence)
- ✅ 2-2 Combos (medium confidence)
- ✅ Inside Bar Setups (low confidence - watch for breakout)

---

## 📁 Required Files

Your GitHub repo needs 4 files:

### 1. server.py
**Use:** `server_with_strat.py` (rename to server.py)

### 2. strat_detector.py
**Use:** `strat_detector.py` (as-is)

### 3. requirements.txt
```
fastapi==0.115.0
uvicorn[standard]==0.32.0
httpx==0.27.2
mcp==1.1.2
pydantic==2.9.2
```

### 4. railway.json
```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn server:app --host 0.0.0.0 --port $PORT",
    "sleepApplication": false,
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE"
  }
}
```

---

## 🚀 Deploy to Railway (15 minutes)

### Step 1: Create GitHub Repo
```bash
# Create new repo on GitHub
# Clone locally and add the 4 files above

git init
git add .
git commit -m "Initial MCP server with STRAT detection"
git branch -M main
git remote add origin YOUR_GITHUB_URL
git push -u origin main
```

### Step 2: Deploy to Railway
1. Go to https://railway.app
2. Sign up/login (GitHub account recommended)
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose your repo
6. Railway auto-detects Python and deploys

### Step 3: Add Environment Variables
In Railway dashboard:
1. Click your service
2. Go to "Variables" tab
3. Add:
   - `ALPACA_API_KEY` = your_key_here
   - `ALPACA_API_SECRET` = your_secret_here
4. Click "Deploy" to restart with new variables

### Step 4: Get Your URL
Railway provides URL like: `https://your-app.up.railway.app`

Your MCP endpoint: `https://your-app.up.railway.app/mcp`

---

## 🔗 Connect to Claude

### On Desktop or Mobile:
1. Go to https://claude.ai
2. Click profile (top right) → Settings
3. Click "Connectors" in sidebar
4. Scroll down → "Add custom connector"
5. Enter:
   - **Name:** Alpaca STRAT Scanner
   - **URL:** `https://your-app.up.railway.app/mcp`
6. Click "Add"
7. Open Claude mobile → New chat → Enable connector

---

## 💬 Example Prompts (Mobile or Desktop)

### Sector Scanning
```
Scan the technology sector for STRAT patterns. 
Show me any stocks with 2-1-2 or 3-1-2 setups.
```

### ETF Analysis
```
Check the top 20 holdings in SPY for STRAT patterns. 
Which ones have bullish setups right now?
```

### Deep Dive Single Stock
```
Analyze NVDA for STRAT patterns. 
Show me the bar types and any actionable setups.
```

### Filtered Pattern Search
```
Scan energy sector stocks for only 2-1-2 reversal patterns
```

### Quick Quote Check
```
Get me current quotes for AAPL, MSFT, NVDA, TSLA, and GOOGL
```

---

## 📊 What Claude Will Tell You

### Example Response Format:

```
**Technology Sector STRAT Scan** - Found 3 stocks with patterns

1. **NVDA** - $485.32
   🟢 **3-1-2 Continuation** (high confidence)
   Direction: BULLISH
   Bullish 3-1-2: Trend continuation breaking to new high $485.32
   Key Level: $485.32

2. **AMD** - $178.45
   🔴 **2-1-2 Reversal** (high confidence)
   Direction: BEARISH
   Bearish 2-1-2: Reversal from high $182.50 through inside bar
   Key Level: $175.20

3. **INTC** - $24.67
   **Inside Bar Setup** (low confidence)
   Inside bar at $24.67 - Watch for breakout
   Key Level: High: $25.10, Low: $24.20
```

---

## 💰 Cost Breakdown

**Railway Starter:** $5/month
- Always-on (no cold starts)
- 128MB RAM allocation
- Unlimited requests at your usage (10 prompts/day = 300 requests)
- First $5 free credit included

**Total monthly cost:** $5-8 depending on actual usage

---

## 🔧 Testing Before Connecting to Claude

Test your deployment:

```bash
# Health check
curl https://your-app.up.railway.app/health

# Test quote (should return error without auth, but proves server is up)
curl https://your-app.up.railway.app/mcp
```

---

## 🐛 Troubleshooting

**Server won't start:**
- Check Railway logs for errors
- Verify all 4 files are in repo
- Ensure requirements.txt has correct versions

**No patterns detected:**
- Market might be quiet (normal)
- Try different sectors or timeframes
- Check Alpaca API keys are valid

**Rate limit errors:**
- You have 200 req/min with Alpaca paid
- 10 prompts/day won't hit this
- If scanning 50+ stocks, add delays (already implemented)

**Claude can't connect:**
- Verify URL ends with `/mcp`
- Check Railway service is "Active" not "Sleeping"
- Test health endpoint first

---

## 🎯 Next Steps After Deployment

Once working, you can expand:

1. **Add hourly STRAT scanning** (change timeframe to "1Hour")
2. **Add multi-timeframe analysis** (check weekly + daily alignment)
3. **Add volume confirmation** to pattern detection
4. **Cache historical data** with Railway Redis ($5/mo) to speed up scans
5. **Add portfolio tracking** if you want position analysis

---

## 📝 Important Notes

- Patterns detected are **existing/completed** not predictions
- High confidence = 2-1-2 or 3-1-2 patterns
- Always verify with your own STRAT analysis before trading
- Data is 15-min delayed (IEX feed) unless you have Alpaca real-time subscription
- Scans during market hours get freshest data

---

## ✅ Deployment Checklist

- [ ] Created GitHub repo with 4 files
- [ ] Deployed to Railway
- [ ] Added Alpaca API keys to Railway variables
- [ ] Verified health endpoint returns {"status": "healthy"}
- [ ] Added connector to claude.ai
- [ ] Tested with sample prompt on mobile
- [ ] Confirmed STRAT patterns are being detected

---

**You're ready to scan for STRAT patterns from anywhere!**

Next Claude conversation: "Scan the technology sector for STRAT patterns"
