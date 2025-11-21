# STRAT Stock Scanner

Production-ready MCP server providing systematic technical analysis using Rob Smith's STRAT methodology with OAuth 2.1 authentication and intelligent rate limiting.

## Overview

Remote MCP server enabling real-time stock analysis using the STRAT methodology. Deploy once to Railway and access from Claude Desktop or mobile anywhere with an internet connection. Designed for traders requiring mobile-accessible pattern detection and multi-timeframe analysis.

**Version:** 2.1.0 - Multi-timeframe continuity analysis with corrected bar classification

## Features

### Core Features
- Real-time stock quotes via Alpaca API
- STRAT pattern detection (2-1-2, 3-1-2, 2-2, Rev Strats)
- Timeframe Continuity (TFC) analysis across 5 timeframes (monthly, weekly, daily, 60min, 15min)
- Multi-timeframe alignment scoring (0-5 scale with quality grades)
- Sector-wide scanning (up to 100 stocks per scan)
- ETF holdings analysis (SPY, QQQ, IWM, etc.)
- ATR and volume filtering for scanner results
- Bulk quote lookups (up to 50 stocks)
- Mobile-accessible via Claude MCP connector

### Production Features (v2.0)
- OAuth 2.1 authentication with PKCE (MCP spec-compliant)
- Intelligent rate limiting (180 requests/minute, safely under Alpaca's 200 limit)
- Exponential backoff on rate limit errors
- Concurrent request limiting (max 3 simultaneous)
- Automatic retry logic with configurable attempts
- Comprehensive error handling

## STRAT Patterns Detected

### High Confidence
- **2-1-2 Reversals**: 2U/2D → 1 → 2U/2D (reversal direction, live entry at inside bar high/low)
- **3-1-2 Continuations**: 3 → 1 → 2U/2D (same direction, live entry at inside bar high/low)

### Medium Confidence
- **2-2 Combos**: Consecutive 2U or 2D bars (directional momentum, entry after bar close)
- **Rev Strats**: Reversal patterns based on multi-bar sequences

### Timeframe Continuity
- **TFC Scores**: 0-5 alignment across monthly, weekly, daily, 60min, 15min
- **Quality Grades**: A+ (5/5), A (4/5), B (3/5), C (2/5), D (0-1/5)
- **Directional Bias**: Bullish, bearish, or neutral based on dominant pattern alignment

## Project Structure

```
strat-stock-scanner/
├── server.py              # Main MCP server with FastAPI
├── config.py              # Configuration management
├── auth_server.py         # OAuth 2.1 authorization server
├── auth_middleware.py     # JWT token validation
├── rate_limiter.py        # Intelligent rate limiting
├── alpaca_client.py       # Alpaca API wrapper with rate limiting
├── mcp_tools.py           # MCP tool definitions
├── strat_detector.py      # STRAT pattern detection engine
├── requirements.txt       # Python dependencies
├── pyproject.toml         # UV package configuration
├── railway.json           # Railway deployment config
├── .env.example           # Environment variable template
├── test_local.py          # Local testing script
├── tests/                 # Unit and integration tests
│   ├── test_auth.py
│   ├── test_rate_limiter.py
│   └── test_integration.py
├── docs/
│   ├── claude.md          # Development guidelines
│   └── DEPLOYMENT.md      # Deployment instructions
└── .claude/
    ├── mcp.json           # MCP server configuration
    └── skills/
        └── strat-methodology/  # STRAT expertise skill
```

## Setup

### Prerequisites

- Python 3.10+
- UV package manager
- Alpaca Markets account (paper or live)
- Railway account (for deployment)

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/strat-stock-scanner.git
cd strat-stock-scanner
```

2. **Install dependencies**
```bash
uv sync
```

3. **Generate OAuth secrets**
```bash
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('OAUTH_CLIENT_SECRET=' + secrets.token_urlsafe(32))"
```

4. **Create .env file** (copy from .env.example)
```bash
cp .env.example .env
# Edit .env and add your credentials
```

Required environment variables:
```bash
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_API_SECRET=your_alpaca_api_secret
JWT_SECRET_KEY=generated_secret_from_step_3
OAUTH_CLIENT_SECRET=generated_secret_from_step_3
```

5. **Run the server**
```bash
uv run python server.py
```

6. **Test locally**
```bash
# Run comprehensive local tests
uv run python test_local.py

# Or test individual endpoints
curl http://localhost:8080/health
curl http://localhost:8080/.well-known/oauth-protected-resource

# Run unit tests
pytest tests/
```

### Railway Deployment

See `docs/DEPLOYMENT.md` for complete deployment instructions.

**Quick Start:**

1. **Generate OAuth secrets locally:**
```bash
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('OAUTH_CLIENT_SECRET=' + secrets.token_urlsafe(32))"
```

2. **Create GitHub repository** with project files

3. **Connect to Railway** and create new project

4. **Add environment variables in Railway dashboard:**
   - `ALPACA_API_KEY` - Your Alpaca API key
   - `ALPACA_API_SECRET` - Your Alpaca API secret
   - `JWT_SECRET_KEY` - Generated secret from step 1
   - `OAUTH_CLIENT_SECRET` - Generated secret from step 1
   - `OAUTH_CLIENT_ID` - `claude-mcp-client` (default)

5. **Deploy automatically** - Railway builds and deploys from GitHub

6. **Verify deployment:**
```bash
curl https://your-app.up.railway.app/health
curl https://your-app.up.railway.app/.well-known/oauth-protected-resource
```

7. **Get your MCP URL:** `https://your-app.up.railway.app/mcp`

## Usage

### Connect to Claude

1. Go to https://claude.ai → Settings → Connectors

2. Add custom connector:
   - **Name:** Alpaca STRAT Scanner
   - **URL:** `https://your-app.up.railway.app/mcp`

3. **Complete OAuth flow:**
   - Claude will redirect you to the authorization endpoint
   - You'll be redirected back with an authorization code
   - Claude exchanges the code for an access token
   - Token is valid for 1 hour, refresh token lasts 30 days

4. Enable connector in new chat

5. Scanner is now available on mobile and desktop

### Example Prompts

**Sector Scanning:**
```
Scan the technology sector for STRAT patterns.
Show me any 2-1-2 or 3-1-2 setups.
```

**ETF Analysis:**
```
Check the top 20 holdings in SPY for STRAT patterns.
Which ones have bullish setups?
```

**Single Stock Analysis:**
```
Analyze NVDA for STRAT patterns on the daily chart.
```

**Filtered Search:**
```
Scan energy sector for only 2-1-2 reversal patterns.
```

**Bulk Quotes:**
```
Get current quotes for AAPL, MSFT, NVDA, TSLA, GOOGL
```

**Timeframe Continuity Analysis:**
```
Analyze AAPL for timeframe continuity across all 5 timeframes.
Which timeframes are aligned bullish?
```

**TFC Scanner:**
```
Scan technology sector for stocks with 4/5 or 5/5 bullish TFC alignment.
Filter for minimum 2% ATR and $50M daily volume.
```

## MCP Tools

### get_stock_quote
Get real-time bid/ask prices for a single stock.

**Parameters:**
- `ticker`: Stock symbol (e.g., 'AAPL')

### analyze_strat_patterns
Deep STRAT analysis on a single stock with bar classification.

**Parameters:**
- `ticker`: Stock symbol
- `timeframe`: '1Day' or '1Hour' (default: '1Day')
- `days_back`: History to analyze (default: 10)

### analyze_tfc
Analyze Timeframe Continuity across 5 timeframes (monthly, weekly, daily, 60min, 15min).

**Parameters:**
- `ticker`: Stock symbol
- `include_monthly`: Include monthly timeframe (default: true, requires ~120 days data)
- `include_weekly`: Include weekly timeframe (default: true, requires ~60 days data)

**Returns:**
- TFC score (0-5) with quality grade
- Dominant directional bias (bullish/bearish/neutral)
- Pattern details for each timeframe
- Stock metrics (price, ATR, volume)

### scan_for_tfc_alignment
Scan multiple stocks for timeframe continuity alignment.

**Parameters:**
- `tickers`: List of stock symbols to scan
- `min_score`: Minimum TFC score (1-5, default: 3 for 3/5 alignment)
- `direction`: Filter by direction ('bullish', 'bearish', 'any')
- `include_monthly`: Include monthly timeframe (default: true)
- `min_atr`: Minimum ATR in dollars (default: 0.0)
- `min_atr_percent`: Minimum ATR as percentage of price (default: 0.0)
- `min_dollar_volume`: Minimum daily dollar volume (default: 0.0)

**Returns:**
- Ranked list of stocks by TFC score and ATR percentage
- Aligned timeframes for each stock
- Stock metrics and pattern details

### scan_sector_for_strat
Scan entire sector for STRAT patterns with intelligent rate limiting.

**Parameters:**
- `sector`: Sector name (technology, healthcare, energy, etc.)
- `top_n`: Number of stocks to scan (default: 20, max: 100)
- `pattern_filter`: Optional ('2-1-2', '3-1-2', '2-2', 'inside')
- `min_atr`: Minimum ATR in dollars (default: 0.0)
- `min_atr_percent`: Minimum ATR as percentage of price (default: 0.0)
- `min_dollar_volume`: Minimum daily dollar volume (default: 0.0)

**Rate Limiting:**
- Automatically throttled to stay under 180 requests/minute
- Progress logging every 10 stocks
- Safe for large scans (100+ stocks)

### scan_etf_holdings_strat
Scan ETF top holdings for patterns.

**Parameters:**
- `etf`: ETF symbol (SPY, QQQ, IWM, XLK, XLF, XLE, XLV)
- `top_n`: Number of holdings to scan (default: 30)
- `min_atr`: Minimum ATR in dollars (default: 0.0)
- `min_atr_percent`: Minimum ATR as percentage of price (default: 0.0)
- `min_dollar_volume`: Minimum daily dollar volume (default: 0.0)

### get_multiple_quotes
Bulk quote lookup (up to 50 stocks).

**Parameters:**
- `tickers`: List of stock symbols

## Technical Details

### Bar Classification

**Type 1 (Inside Bar):**
- High <= Previous High AND Low >= Previous Low
- Breaks neither bound
- Consolidation/indecision, watch for breakout

**Type 2U (Directional Up):**
- High > Previous High AND Low >= Previous Low
- Breaks high only
- Bullish directional move

**Type 2D (Directional Down):**
- High <= Previous High AND Low < Previous Low
- Breaks low only
- Bearish directional move

**Type 3 (Outside Bar):**
- High > Previous High AND Low < Previous Low
- Breaks both high and low
- Expansion/volatility bar

### Timeframe Continuity Scoring

**TFC Score Calculation:**
- Each timeframe adds 1 point if aligned in same direction
- Maximum score: 5/5 (all timeframes aligned)
- Minimum for quality setups: 3/5 (3 timeframes aligned)

**Quality Grades:**
- A+ (5/5): Perfect alignment across all timeframes
- A (4/5): Strong alignment, 4 timeframes agree
- B (3/5): Good alignment, 3 timeframes agree
- C (2/5): Weak alignment, only 2 timeframes
- D (0-1/5): No meaningful alignment

### Data Source

- **Alpaca Markets API** (paper or live account)
- **IEX Feed:** Free tier (15-min delay)
- **SIP Feed:** Paid subscription (real-time)
- **Rate Limit:** 200 requests/minute (paper trading)
- **Our Limit:** 180 requests/minute (safety buffer)
- **Concurrent Requests:** Max 3 simultaneous
- **Retry Logic:** Exponential backoff on errors

### Cost Breakdown

**Railway Hosting:** $5/month
- Always-on (no cold starts)
- 128MB RAM allocation
- Unlimited requests at typical usage
- First $5 free credit included

**Alpaca API:** Free (paper trading)
- 200 requests/minute
- Real-time quotes (with subscription)
- Historical data access

**Total Monthly Cost:** $5-8

## Development

### Adding New STRAT Patterns

1. Research pattern in `.claude/skills/strat-methodology/PATTERNS.md`
2. Implement detection in `strat_detector.py`
3. Test with known examples
4. Validate with live Alpaca data

See `docs/claude.md` for development guidelines.

### Testing

**Local Testing:**
```bash
# Run comprehensive local test suite
uv run python test_local.py

# This will test:
# - Alpaca API connection
# - Historical bar retrieval
# - STRAT pattern detection
# - Rate limiter with 10 concurrent requests
# - OAuth secret generation
```

**Unit Tests:**
```bash
# Run all tests
pytest tests/

# Run specific test files
pytest tests/test_rate_limiter.py
pytest tests/test_auth.py
pytest tests/test_integration.py

# Run with verbose output
pytest tests/ -v
```

**MCP Inspector:**
```bash
# Test MCP server with inspector
npx @modelcontextprotocol/inspector uv run python server.py
```

## Important Notes

- Patterns detected are **existing/completed**, not predictions
- High confidence = 2-1-2 or 3-1-2 patterns (most reliable)
- Always verify with your own STRAT analysis before trading
- Data is 15-min delayed (IEX) unless using real-time subscription
- Scans during market hours get freshest data

### Security

- OAuth 2.1 with PKCE prevents authorization code interception
- JWT tokens expire after 1 hour for security
- Refresh tokens valid for 30 days
- All MCP endpoints require authentication
- Never commit secrets to git (use .env file locally)
- Railway environment variables are encrypted at rest

### Rate Limiting

- Automatically stays under Alpaca's 200 req/min limit
- Safe to scan 100+ stocks without hitting rate limits
- Exponential backoff on 429 rate limit errors
- Maximum 3 concurrent requests to prevent overload
- Progress logging for large scans

## Contributing

Contributions are welcome. When contributing:

1. Follow professional development standards (no emojis in code, plain ASCII text only)
2. Test thoroughly with the local test suite before submitting
3. Include unit tests for new features
4. Update documentation to reflect changes
5. Use conventional commit format (feat:, fix:, docs:, test:, refactor:)

## License

MIT License - See LICENSE file for details

## Disclaimer

This software is for educational and informational purposes only. It is not financial advice. Always conduct your own research and consult with a licensed financial advisor before making investment decisions. The authors are not responsible for any financial losses incurred from using this software.

## Contact

For questions or issues, please open a GitHub issue.

---

**Built with STRAT methodology** - Making technical analysis systematic and mobile-accessible.
