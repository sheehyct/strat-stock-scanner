# STRAT Stock Scanner

Mobile-accessible stock scanner using STRAT methodology and Alpaca Markets API.

## Overview

This project provides real-time stock scanning capabilities using Rob Smith's STRAT methodology. The scanner is deployed as a remote MCP server on Railway, making it accessible from Claude mobile/desktop anywhere with an internet connection.

**Use Case:** Firefighter/trader needing mobile access to STRAT pattern detection during 24-hour shifts.

## Features

- Real-time stock quotes via Alpaca API
- STRAT pattern detection (2-1-2, 3-1-2, 2-2, inside bars)
- Sector-wide scanning (Technology, Healthcare, Energy, etc.)
- ETF holdings analysis (SPY, QQQ, IWM, etc.)
- Bulk quote lookups
- Mobile-accessible via Claude MCP connector

## STRAT Patterns Detected

### High Confidence
- **2-1-2 Reversals**: Outside bar → Inside bar → Outside bar (opposite direction)
- **3-1-2 Continuations**: Directional bar → Inside bar → Outside bar (same direction)

### Medium Confidence
- **2-2 Combos**: Consecutive outside bars (volatile expansion)

### Low Confidence
- **Inside Bar Setups**: Watch for breakout direction

## Project Structure

```
strat-stock-scanner/
├── server.py              # Main MCP server with FastAPI
├── strat_detector.py      # STRAT pattern detection engine
├── requirements.txt       # Python dependencies
├── pyproject.toml        # UV package configuration
├── railway.json          # Railway deployment config
├── docs/
│   ├── claude.md         # Development guidelines
│   └── DEPLOYMENT.md     # Deployment instructions
└── .claude/
    ├── mcp.json          # MCP server configuration
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

3. **Set environment variables**
```bash
export ALPACA_API_KEY="your_key_here"
export ALPACA_API_SECRET="your_secret_here"
```

4. **Run the server**
```bash
uv run python server.py
```

5. **Test locally**
```bash
# Health check
curl http://localhost:8080/health

# MCP endpoint
curl http://localhost:8080/mcp
```

### Railway Deployment

See `docs/DEPLOYMENT.md` for complete deployment instructions.

**Quick Start:**

1. Create GitHub repository with project files
2. Connect to Railway
3. Add environment variables:
   - `ALPACA_API_KEY`
   - `ALPACA_API_SECRET`
4. Deploy automatically
5. Get your URL: `https://your-app.up.railway.app/mcp`

## Usage

### Connect to Claude

1. Go to https://claude.ai → Settings → Connectors
2. Add custom connector:
   - **Name:** Alpaca STRAT Scanner
   - **URL:** `https://your-app.up.railway.app/mcp`
3. Enable connector in new chat
4. Scanner is now available on mobile and desktop

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

### scan_sector_for_strat
Scan entire sector for STRAT patterns.

**Parameters:**
- `sector`: Sector name (technology, healthcare, energy, etc.)
- `top_n`: Number of stocks to scan (default: 20, max: 50)
- `pattern_filter`: Optional ('2-1-2', '3-1-2', '2-2', 'inside')

### scan_etf_holdings_strat
Scan ETF top holdings for patterns.

**Parameters:**
- `etf`: ETF symbol (SPY, QQQ, IWM, XLK, XLF, XLE, XLV)
- `top_n`: Number of holdings to scan (default: 30)

### get_multiple_quotes
Bulk quote lookup (up to 50 stocks).

**Parameters:**
- `tickers`: List of stock symbols

## Technical Details

### Bar Classification

**Type 1 (Inside Bar):**
- High < Previous High AND Low > Previous Low
- Consolidation/indecision
- Watch for breakout

**Type 2U (Outside Bar Up):**
- High > Previous High AND Low <= Previous Low
- Bullish expansion

**Type 2D (Outside Bar Down):**
- High >= Previous High AND Low < Previous Low
- Bearish expansion

**Type 3 (Directional):**
- Neither inside nor outside
- Continuation or new direction

### Data Source

- **Alpaca Markets API** (paper or live account)
- **IEX Feed:** Free tier (15-min delay)
- **SIP Feed:** Paid subscription (real-time)
- Rate limit: 200 requests/minute (paper trading)

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

```bash
# Run MCP inspector locally
npx @modelcontextprotocol/inspector uv run python server.py

# Test pattern detection
uv run python -c "from strat_detector import STRATDetector; print('Pattern detector loaded')"
```

## Important Notes

- Patterns detected are **existing/completed**, not predictions
- High confidence = 2-1-2 or 3-1-2 patterns (most reliable)
- Always verify with your own STRAT analysis before trading
- Data is 15-min delayed (IEX) unless using real-time subscription
- Scans during market hours get freshest data

## Future Enhancements

- Multi-timeframe analysis (daily + weekly alignment)
- Volume confirmation for pattern confidence
- Caching layer with Railway Redis
- Portfolio integration (track existing positions)
- Webhook alerts for watchlist patterns

## Contributing

This is a personal project, but suggestions are welcome. Please follow the development guidelines in `docs/claude.md`.

## License

MIT License - See LICENSE file for details

## Disclaimer

This software is for educational and informational purposes only. It is not financial advice. Always conduct your own research and consult with a licensed financial advisor before making investment decisions. The authors are not responsible for any financial losses incurred from using this software.

## Contact

For questions or issues, please open a GitHub issue.

---

**Built with STRAT methodology** - Making technical analysis systematic and mobile-accessible.
