"""
MCP Tool definitions for STRAT Stock Scanner
All tools use rate-limited Alpaca client
Includes ATR/Volume filtering and multi-timeframe TFC analysis
"""

from typing import List, Optional
import asyncio
from alpaca_client import alpaca
from strat_detector import (
    STRATDetector,
    format_pattern_report,
    format_tfc_report,
    StockMetrics,
    TFCScore
)


async def get_stock_quote(ticker: str) -> str:
    """
    Get real-time stock quote with current price and bid/ask spread.

    Args:
        ticker: Stock symbol (e.g., 'AAPL', 'MSFT', 'SPY')
    """
    quote = await alpaca.get_quote(ticker, feed="iex")

    if not quote:
        return f"Error fetching quote for {ticker}"

    return f"""**{ticker.upper()} Quote**
Bid: ${quote['bp']:.2f} x {quote['bs']}
Ask: ${quote['ap']:.2f} x {quote['as']}
Spread: ${quote['ap'] - quote['bp']:.2f}
Time: {quote['t']}"""


async def analyze_strat_patterns(
    ticker: str,
    timeframe: str = "1Day",
    days_back: int = 10
) -> str:
    """
    Analyze a single stock for STRAT patterns with detailed bar classification.

    Args:
        ticker: Stock symbol (e.g., 'AAPL', 'TSLA')
        timeframe: Bar timeframe - '1Day' for daily, '1Hour' for hourly
        days_back: Number of days of history to analyze

    Returns:
        Detailed STRAT pattern analysis with bar types and setups
    """
    print(f"🔍 [TOOL ENTRY] analyze_strat_patterns: ticker={ticker}, timeframe={timeframe}, days_back={days_back}")

    try:
        # Fetch historical bars using rate-limited client
        print(f"📊 [API CALL] Fetching bars for {ticker}...")
        bars = await alpaca.get_bars_recent(
            ticker,
            days_back=days_back,
            timeframe=timeframe,
            feed="sip"
        )

        print(f"✅ [API RESPONSE] Received {len(bars) if bars else 0} bars for {ticker}")

        if not bars:
            print(f"⚠️ [WARNING] No data returned for {ticker}")
            return f"No data available for {ticker}"
    except Exception as e:
        print(f"❌ [ERROR] analyze_strat_patterns failed: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

    # Detect patterns
    patterns = STRATDetector.scan_for_patterns(bars)

    # Get current price and metrics
    current_price = bars[-1]['c']
    metrics = STRATDetector.get_stock_metrics(ticker, bars)

    if not patterns:
        return f"**{ticker}** - ${current_price:.2f}\nMetrics: {metrics}\nNo STRAT patterns detected in last {days_back} bars"

    # Format report
    report = f"**{ticker} STRAT Analysis** (${current_price:.2f})\n"
    report += f"Timeframe: {timeframe} | Analyzed: {len(bars)} bars\n"
    report += f"Metrics: {metrics}\n\n"

    for i, pattern in enumerate(patterns, 1):
        emoji = "BULLISH" if pattern.direction == "bullish" else "BEARISH"
        report += f"{i}. {emoji} **{pattern.pattern_type}**\n"
        report += f"   Direction: {pattern.direction.upper()}\n"
        report += f"   Confidence: {pattern.confidence}\n"
        report += f"   {pattern.description}\n"
        report += f"   Key Level: ${pattern.entry_level:.2f}\n\n"

    # Show recent bar sequence
    classified_bars = STRATDetector.classify_bars(bars[-5:])
    report += "**Recent Bar Sequence:**\n"
    for bar in classified_bars:
        bar_date = bar.timestamp.split('T')[0]
        report += f"  {bar_date}: Type {bar.bar_type} (H:${bar.high:.2f} L:${bar.low:.2f} C:${bar.close:.2f})\n"

    return report


async def analyze_tfc(
    ticker: str,
    include_weekly: bool = True
) -> str:
    """
    Analyze Timeframe Continuity (TFC) across multiple timeframes.

    Fetches Weekly, Daily, 60min, and 15min data to score alignment.

    Args:
        ticker: Stock symbol (e.g., 'AAPL', 'SPY')
        include_weekly: Whether to include weekly timeframe (requires more data)

    Returns:
        TFC score and breakdown by timeframe
    """
    print(f"🔍 [TOOL ENTRY] analyze_tfc: ticker={ticker}")

    timeframe_data = {}

    try:
        # Fetch each timeframe
        # Weekly - need ~60 days to get enough weekly bars
        if include_weekly:
            print(f"📊 Fetching weekly bars for {ticker}...")
            weekly_bars = await alpaca.get_bars_recent(
                ticker, days_back=60, timeframe="1Week", feed="sip"
            )
            timeframe_data["weekly"] = weekly_bars if weekly_bars else []

        # Daily - 20 days for pattern detection + ATR
        print(f"📊 Fetching daily bars for {ticker}...")
        daily_bars = await alpaca.get_bars_recent(
            ticker, days_back=20, timeframe="1Day", feed="sip"
        )
        timeframe_data["daily"] = daily_bars if daily_bars else []

        # 60min - 10 days worth
        print(f"📊 Fetching 60min bars for {ticker}...")
        h60_bars = await alpaca.get_bars_recent(
            ticker, days_back=10, timeframe="1Hour", feed="sip"
        )
        timeframe_data["60min"] = h60_bars if h60_bars else []

        # 15min - 5 days worth
        print(f"📊 Fetching 15min bars for {ticker}...")
        m15_bars = await alpaca.get_bars_recent(
            ticker, days_back=5, timeframe="15Min", feed="sip"
        )
        timeframe_data["15min"] = m15_bars if m15_bars else []

    except Exception as e:
        print(f"❌ [ERROR] analyze_tfc failed: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

    # Calculate TFC score
    tfc = STRATDetector.calculate_tfc_score(timeframe_data)

    # Get metrics from daily bars
    metrics = None
    if timeframe_data.get("daily"):
        metrics = STRATDetector.get_stock_metrics(ticker, timeframe_data["daily"])

    # Format report
    report = format_tfc_report(ticker, tfc, metrics)

    # Add pattern details for each timeframe
    report += "\n**Pattern Details:**\n"

    tf_names = {"weekly": "Weekly", "daily": "Daily", "60min": "60min", "15min": "15min"}
    for tf_key, tf_name in tf_names.items():
        bars = timeframe_data.get(tf_key, [])
        if bars:
            patterns = STRATDetector.scan_for_patterns(bars)
            if patterns:
                top_pattern = patterns[0]
                direction = "[BULL]" if top_pattern.direction == "bullish" else "[BEAR]"
                report += f"  {direction} {tf_name}: {top_pattern.pattern_type} ({top_pattern.confidence})\n"
            else:
                report += f"  [NONE] {tf_name}: No pattern\n"
        else:
            report += f"  [----] {tf_name}: No data\n"

    return report


async def scan_sector_for_strat(
    sector: str,
    top_n: int = 20,
    pattern_filter: Optional[str] = None,
    min_atr: float = 0.0,
    min_atr_percent: float = 0.0,
    min_dollar_volume: float = 0.0
) -> str:
    """
    Scan sector stocks for STRAT patterns with ATR/volume filtering.

    Args:
        sector: Sector name (technology, healthcare, energy, financials, consumer, industrials, materials, utilities, real_estate, communications)
        top_n: Number of stocks to scan (default 20, max 100)
        pattern_filter: Optional filter - '2-1-2' or '3-1-2' or '2-2' or 'inside' (defaults to all)
        min_atr: Minimum ATR in dollars (e.g., 2.0 for $2 minimum daily range)
        min_atr_percent: Minimum ATR as % of price (e.g., 1.5 for 1.5% minimum)
        min_dollar_volume: Minimum dollar volume (e.g., 20000000 for $20M)

    Returns:
        List of stocks showing STRAT patterns with entry levels and metrics
    """
    # Sector ETF mappings
    sector_tickers = {
        "technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "AVGO", "ORCL", "AMD", "CRM",
                       "ADBE", "NFLX", "INTC", "CSCO", "ACN", "IBM", "NOW", "QCOM", "TXN", "INTU",
                       "AMAT", "MU", "LRCX", "KLAC", "SNPS", "CDNS", "MCHP", "FTNT", "PANW", "CRWD"],
        "healthcare": ["UNH", "JNJ", "LLY", "ABBV", "MRK", "TMO", "ABT", "DHR", "PFE", "BMY",
                       "AMGN", "CVS", "MDT", "GILD", "CI", "REGN", "SYK", "VRTX", "ZTS", "HUM",
                       "BSX", "ELV", "ISRG", "MCK", "CVS", "HCA", "COR", "EW", "A", "IQV"],
        "financials": ["JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "CB", "AXP",
                       "PNC", "USB", "TFC", "COF", "BK", "AIG", "MET", "AFL", "PRU", "ALL",
                       "CME", "SPGI", "ICE", "MCO", "AON", "MMC", "TRV", "PGR", "AJG", "WRB"],
        "energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "WMB",
                   "HAL", "DVN", "HES", "FANG", "BKR", "KMI", "MRO", "APA", "EQT", "CTRA",
                   "OKE", "LNG", "TRGP", "EPD", "ET", "EXE", "XEC", "CVE", "CNQ", "SU"],
        "consumer": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "TJX", "BKNG",
                     "CMG", "MAR", "ORLY", "AZO", "YUM", "ROST", "DHI", "LEN", "F", "GM",
                     "EBAY", "COST", "WMT", "PG", "KO", "PEP", "MDLZ", "CL", "EL", "CLX"],
        "industrials": ["CAT", "GE", "RTX", "UNP", "BA", "HON", "LMT", "DE", "UPS", "ADP",
                        "MMM", "GD", "ETN", "ITW", "EMR", "PCAR", "NOC", "FDX", "CSX", "WM",
                        "NSC", "TT", "PH", "JCI", "CARR", "OTIS", "ROK", "AME", "FAST", "PWR"],
        "materials": ["LIN", "APD", "SHW", "FCX", "ECL", "NEM", "CTVA", "DD", "NUE", "VMC",
                      "MLM", "PPG", "ALB", "CF", "MOS", "FMC", "IFF", "EMN", "CE", "AVY"],
        "utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "ED", "PEG",
                      "WEC", "ES", "AWK", "DTE", "EIX", "FE", "ETR", "PPL", "AEE", "CMS"],
        "real_estate": ["PLD", "AMT", "CCI", "EQIX", "PSA", "WELL", "DLR", "O", "SBAC", "AVB",
                        "EQR", "SPG", "VTR", "ARE", "INVH", "MAA", "ESS", "KIM", "REG", "BXP"],
        "communications": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR", "EA",
                          "TTWO", "OMC", "IPG", "FOXA", "PARA", "WBD", "LYV", "NWSA", "MTCH", "PINS"]
    }

    # Get tickers for sector
    tickers = sector_tickers.get(sector.lower(), sector_tickers["technology"])[:min(top_n, 100)]

    results = []
    filtered_count = 0
    completed = 0
    total = len(tickers)

    # Scan each stock for patterns (rate limiter handles throttling)
    # Fetch more days for ATR calculation
    for ticker in tickers:
        bars = await alpaca.get_bars_recent(ticker, days_back=20, timeframe="1Day")

        if not bars:
            completed += 1
            continue

        # Calculate metrics
        metrics = STRATDetector.get_stock_metrics(ticker, bars)

        # Apply ATR/volume filter
        if not metrics.passes_filter(min_atr, min_atr_percent, min_dollar_volume):
            filtered_count += 1
            completed += 1
            continue

        # Detect patterns
        patterns = STRATDetector.scan_for_patterns(bars)

        if patterns:
            # Apply pattern filter if specified
            if pattern_filter:
                patterns = [p for p in patterns if pattern_filter.lower() in p.pattern_type.lower()]

            if patterns:
                current_price = bars[-1]['c']
                results.append({
                    "ticker": ticker,
                    "price": current_price,
                    "patterns": patterns,
                    "metrics": metrics
                })

        completed += 1
        # Progress logging every 10 stocks
        if completed % 10 == 0:
            print(f"Sector scan progress: {completed}/{total} stocks scanned")

    if not results:
        filter_text = f" matching '{pattern_filter}'" if pattern_filter else ""
        filter_info = ""
        if min_atr > 0 or min_atr_percent > 0 or min_dollar_volume > 0:
            filter_info = f" ({filtered_count} filtered by ATR/volume)"
        return f"No STRAT patterns{filter_text} found in {sector} sector stocks{filter_info}"

    # Format output
    output = f"**{sector.title()} Sector STRAT Scan** - Found {len(results)} stocks with patterns\n"
    if filtered_count > 0:
        output += f"({filtered_count} stocks filtered by ATR/volume requirements)\n"
    output += "\n"

    for i, stock in enumerate(results, 1):
        output += f"{i}. {format_pattern_report(stock['ticker'], stock['patterns'], stock['price'], stock['metrics'])}\n"

    return output


async def scan_etf_holdings_strat(
    etf: str,
    top_n: int = 30,
    min_atr: float = 0.0,
    min_atr_percent: float = 0.0,
    min_dollar_volume: float = 0.0
) -> str:
    """
    Scan top holdings of an ETF for STRAT patterns with ATR/volume filtering.

    Args:
        etf: ETF symbol (e.g., 'SPY', 'QQQ', 'IWM', 'XLK', 'XLF')
        top_n: Number of top holdings to scan
        min_atr: Minimum ATR in dollars (e.g., 2.0 for $2 minimum daily range)
        min_atr_percent: Minimum ATR as % of price (e.g., 1.5 for 1.5% minimum)
        min_dollar_volume: Minimum dollar volume (e.g., 20000000 for $20M)

    Returns:
        STRAT patterns found in ETF holdings with metrics
    """
    # Common ETF holdings (simplified - top holdings)
    etf_holdings = {
        "SPY": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK.B", "AVGO", "LLY", "TSLA",
                "JPM", "WMT", "V", "XOM", "UNH", "MA", "PG", "COST", "JNJ", "HD"],
        "QQQ": ["AAPL", "MSFT", "NVDA", "AMZN", "META", "AVGO", "TSLA", "GOOGL", "COST", "NFLX",
                "AMD", "PEP", "ADBE", "CSCO", "TMUS", "INTC", "CMCSA", "TXN", "INTU", "AMGN"],
        "IWM": ["RELY", "GKOS", "ALKT", "EXLS", "NOVT", "WTFC", "NXST", "UFPI", "STRL", "SHOO",
                "CASY", "AXON", "ESNT", "CRVL", "TGTX", "SAIA", "BOOT", "ATKR", "ONTO", "MTH"],
        "XLK": ["AAPL", "MSFT", "NVDA", "AVGO", "CRM", "ORCL", "AMD", "CSCO", "ACN", "ADBE",
                "IBM", "INTC", "QCOM", "NOW", "TXN", "INTU", "AMAT", "MU", "LRCX", "KLAC"],
        "XLF": ["JPM", "BAC", "WFC", "MS", "GS", "BLK", "C", "SCHW", "CB", "AXP",
                "PNC", "USB", "TFC", "AIG", "COF", "AFL", "MET", "PRU", "ALL", "BK"],
        "XLE": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HAL",
                "WMB", "BKR", "FANG", "DVN", "HES", "KMI", "MRO", "CTRA", "APA", "EQT"],
        "XLV": ["UNH", "LLY", "JNJ", "ABBV", "MRK", "TMO", "ABT", "DHR", "PFE", "BMY",
                "AMGN", "CVS", "MDT", "GILD", "CI", "REGN", "VRTX", "SYK", "ZTS", "HUM"]
    }

    holdings = etf_holdings.get(etf.upper(), etf_holdings["SPY"])[:top_n]

    results = []
    filtered_count = 0
    completed = 0
    total = len(holdings)

    # Scan holdings (rate limiter handles throttling)
    # Fetch more days for ATR calculation
    for ticker in holdings:
        bars = await alpaca.get_bars_recent(ticker, days_back=20, timeframe="1Day")

        if not bars:
            completed += 1
            continue

        # Calculate metrics
        metrics = STRATDetector.get_stock_metrics(ticker, bars)

        # Apply ATR/volume filter
        if not metrics.passes_filter(min_atr, min_atr_percent, min_dollar_volume):
            filtered_count += 1
            completed += 1
            continue

        patterns = STRATDetector.scan_for_patterns(bars)

        if patterns:
            current_price = bars[-1]['c']
            results.append({
                "ticker": ticker,
                "price": current_price,
                "patterns": patterns,
                "metrics": metrics
            })

        completed += 1
        if completed % 10 == 0:
            print(f"ETF scan progress: {completed}/{total} holdings scanned")

    if not results:
        filter_info = ""
        if filtered_count > 0:
            filter_info = f" ({filtered_count} filtered by ATR/volume)"
        return f"No STRAT patterns found in {etf} holdings{filter_info}"

    output = f"**{etf.upper()} Holdings STRAT Scan** - {len(results)} stocks with patterns\n"
    if filtered_count > 0:
        output += f"({filtered_count} stocks filtered by ATR/volume requirements)\n"
    output += "\n"

    for i, stock in enumerate(results, 1):
        output += f"{i}. {format_pattern_report(stock['ticker'], stock['patterns'], stock['price'], stock['metrics'])}\n"

    return output


async def scan_for_tfc_alignment(
    tickers: List[str],
    min_score: int = 3,
    direction: str = "bullish",
    min_atr: float = 0.0,
    min_atr_percent: float = 0.0,
    min_dollar_volume: float = 0.0
) -> str:
    """
    Scan multiple stocks for Timeframe Continuity alignment.

    Finds stocks with 3/4 or 4/4 timeframes aligned in same direction.

    Args:
        tickers: List of stock symbols to scan
        min_score: Minimum TFC score (1-4, default 3 for 3/4 alignment)
        direction: Filter by direction - 'bullish', 'bearish', or 'any'
        min_atr: Minimum ATR in dollars
        min_atr_percent: Minimum ATR as % of price
        min_dollar_volume: Minimum dollar volume

    Returns:
        Ranked list of stocks with TFC scores
    """
    print(f"🔍 [TOOL ENTRY] scan_for_tfc_alignment: {len(tickers)} tickers, min_score={min_score}, direction={direction}")

    results = []
    filtered_count = 0

    for ticker in tickers:
        try:
            # Fetch all timeframes
            timeframe_data = {}

            # Weekly
            weekly_bars = await alpaca.get_bars_recent(
                ticker, days_back=60, timeframe="1Week", feed="sip"
            )
            timeframe_data["weekly"] = weekly_bars if weekly_bars else []

            # Daily (also used for metrics)
            daily_bars = await alpaca.get_bars_recent(
                ticker, days_back=20, timeframe="1Day", feed="sip"
            )
            timeframe_data["daily"] = daily_bars if daily_bars else []

            if not daily_bars:
                continue

            # Calculate metrics and apply filter
            metrics = STRATDetector.get_stock_metrics(ticker, daily_bars)
            if not metrics.passes_filter(min_atr, min_atr_percent, min_dollar_volume):
                filtered_count += 1
                continue

            # 60min
            h60_bars = await alpaca.get_bars_recent(
                ticker, days_back=10, timeframe="1Hour", feed="sip"
            )
            timeframe_data["60min"] = h60_bars if h60_bars else []

            # 15min
            m15_bars = await alpaca.get_bars_recent(
                ticker, days_back=5, timeframe="15Min", feed="sip"
            )
            timeframe_data["15min"] = m15_bars if m15_bars else []

            # Calculate TFC
            tfc = STRATDetector.calculate_tfc_score(timeframe_data)

            # Apply filters
            if tfc.score >= min_score:
                if direction == "any" or tfc.dominant_bias == direction:
                    results.append({
                        "ticker": ticker,
                        "tfc": tfc,
                        "metrics": metrics
                    })

        except Exception as e:
            print(f"⚠️ Error scanning {ticker}: {e}")
            continue

    if not results:
        return f"No stocks found with TFC score >= {min_score} ({direction})"

    # Sort by TFC score (descending), then by ATR% (descending)
    results.sort(key=lambda x: (x['tfc'].score, x['metrics'].atr_percent), reverse=True)

    # Format output
    output = f"**TFC Alignment Scan** - {len(results)} stocks with {min_score}/4+ {direction} alignment\n"
    if filtered_count > 0:
        output += f"({filtered_count} filtered by ATR/volume)\n"
    output += "\n"

    for i, result in enumerate(results, 1):
        tfc = result['tfc']
        metrics = result['metrics']
        ticker = result['ticker']

        bias_marker = "[BULL]" if tfc.dominant_bias == "bullish" else "[BEAR]"
        output += f"{i}. {bias_marker} **{ticker}** - TFC {tfc.score}/4 ({tfc.quality})\n"
        output += f"   Aligned: {', '.join(tfc.aligned_timeframes)}\n"
        output += f"   Metrics: {metrics}\n"

        # Show top pattern from daily
        if timeframe_data.get("daily"):
            patterns = STRATDetector.scan_for_patterns(result.get('daily_bars', []))
            if patterns:
                output += f"   Pattern: {patterns[0].pattern_type} ({patterns[0].confidence})\n"
        output += "\n"

    return output


async def get_multiple_quotes(tickers: List[str]) -> str:
    """
    Get quotes for multiple stocks at once (efficient bulk lookup).

    Args:
        tickers: List of stock symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])
    """
    if len(tickers) > 50:
        return "Error: Maximum 50 tickers per request"

    # Use rate-limited client (handles throttling automatically)
    quotes = await alpaca.get_multiple_quotes(tickers, feed="iex")

    results = []
    for ticker in tickers:
        quote = quotes.get(ticker)
        if quote:
            results.append(
                f"{ticker.upper()}: ${quote['ap']:.2f} (Bid: ${quote['bp']:.2f})"
            )
        else:
            results.append(f"{ticker.upper()}: No data")

    return "\n".join(results)
