"""
STRAT analysis tools for MCP server
Uses rate-limited Alpaca client and STRAT detector
"""

from typing import List, Optional
import asyncio
from alpaca_client import alpaca
from strat_detector import STRATDetector, format_pattern_report


async def get_stock_quote(ticker: str) -> str:
    """
    Get real-time stock quote with current price and bid/ask spread.

    Args:
        ticker: Stock symbol (e.g., 'AAPL', 'MSFT', 'SPY')

    Returns:
        Formatted quote with bid/ask spread
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
    # Fetch historical bars using rate-limited client
    bars = await alpaca.get_bars_recent(
        ticker,
        days_back=days_back,
        timeframe=timeframe,
        feed="sip"
    )

    if not bars:
        return f"No data available for {ticker}"

    # Detect patterns
    patterns = STRATDetector.scan_for_patterns(bars)

    # Get current price from latest bar
    current_price = bars[-1]['c']

    if not patterns:
        return f"**{ticker}** - ${current_price:.2f}\nNo STRAT patterns detected in last {days_back} bars"

    # Format report
    report = f"**{ticker} STRAT Analysis** (${current_price:.2f})\n"
    report += f"Timeframe: {timeframe} | Analyzed: {len(bars)} bars\n\n"

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


async def scan_sector_for_strat(
    sector: str,
    top_n: int = 20,
    pattern_filter: Optional[str] = None
) -> str:
    """
    Scan sector stocks for STRAT patterns - finds existing setups.

    Args:
        sector: Sector name (technology, healthcare, energy, financials, consumer, industrials, materials, utilities, real_estate, communications)
        top_n: Number of stocks to scan (default 20, max 100)
        pattern_filter: Optional filter - '2-1-2' or '3-1-2' or '2-2' or 'inside' (defaults to all)

    Returns:
        List of stocks showing STRAT patterns with entry levels
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
    completed = 0
    total = len(tickers)

    # Scan each stock for patterns (rate limiter handles throttling)
    for ticker in tickers:
        bars = await alpaca.get_bars_recent(ticker, days_back=10, timeframe="1Day")

        if not bars:
            completed += 1
            continue

        # Detect patterns
        patterns = STRATDetector.scan_for_patterns(bars)

        if patterns:
            # Apply filter if specified
            if pattern_filter:
                patterns = [p for p in patterns if pattern_filter.lower() in p.pattern_type.lower()]

            if patterns:
                current_price = bars[-1]['c']
                results.append({
                    "ticker": ticker,
                    "price": current_price,
                    "patterns": patterns
                })

        completed += 1
        # Progress logging every 10 stocks
        if completed % 10 == 0:
            print(f"Sector scan progress: {completed}/{total} stocks scanned")

    if not results:
        filter_text = f" matching '{pattern_filter}'" if pattern_filter else ""
        return f"No STRAT patterns{filter_text} found in {sector} sector stocks"

    # Format output
    output = f"**{sector.title()} Sector STRAT Scan** - Found {len(results)} stocks with patterns\n\n"

    for i, stock in enumerate(results, 1):
        output += f"{i}. {format_pattern_report(stock['ticker'], stock['patterns'], stock['price'])}\n"

    return output


async def scan_etf_holdings_strat(etf: str, top_n: int = 30) -> str:
    """
    Scan top holdings of an ETF for STRAT patterns.

    Args:
        etf: ETF symbol (e.g., 'SPY', 'QQQ', 'IWM', 'XLK', 'XLF')
        top_n: Number of top holdings to scan

    Returns:
        STRAT patterns found in ETF holdings
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
    completed = 0
    total = len(holdings)

    # Scan holdings (rate limiter handles throttling)
    for ticker in holdings:
        bars = await alpaca.get_bars_recent(ticker, days_back=10, timeframe="1Day")

        if not bars:
            completed += 1
            continue

        patterns = STRATDetector.scan_for_patterns(bars)

        if patterns:
            current_price = bars[-1]['c']
            results.append({
                "ticker": ticker,
                "price": current_price,
                "patterns": patterns
            })

        completed += 1
        if completed % 10 == 0:
            print(f"ETF scan progress: {completed}/{total} holdings scanned")

    if not results:
        return f"No STRAT patterns found in {etf} holdings"

    output = f"**{etf.upper()} Holdings STRAT Scan** - {len(results)} stocks with patterns\n\n"

    for i, stock in enumerate(results, 1):
        output += f"{i}. {format_pattern_report(stock['ticker'], stock['patterns'], stock['price'])}\n"

    return output


async def get_multiple_quotes(tickers: List[str]) -> str:
    """
    Get quotes for multiple stocks at once (efficient bulk lookup).

    Args:
        tickers: List of stock symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])

    Returns:
        Formatted list of quotes
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
