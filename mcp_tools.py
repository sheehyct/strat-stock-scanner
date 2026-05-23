"""
MCP Tool definitions for STRAT Stock Scanner.

All data calls go through the Tradier client (see tradier_client.py). The bar
and quote shapes returned by the client are the same dict shape the STRAT
detector already expects (keys: t, o, h, l, c, v for bars; bp, bs, ap, as, t
for quotes), so this module changes only the data source — not the analysis
or output contracts.

Every catch block must log via logger.exception() before returning a
user-facing error string. This is the explicit fix for the silent-failure
mode that motivated the migration from Alpaca.
"""

import logging
from datetime import datetime, time

import pytz
from strat_detector import (
    STRATDetector,
    format_pattern_report,
    format_tfc_report,
)
from tradier_client import tradier

logger = logging.getLogger(__name__)


def _get_session_type(timestamp_str: str) -> str:
    """Classify a quote timestamp as regular / pre-market / post-market /
    unknown based on US/Eastern wall-clock time."""
    if not timestamp_str:
        return "unknown"
    try:
        et = pytz.timezone("America/New_York")
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        dt_et = dt.astimezone(et)
        market_open = time(9, 30)
        market_close = time(16, 0)
        if dt_et.time() < market_open:
            return "pre-market"
        elif dt_et.time() >= market_close:
            return "post-market"
        return "regular"
    except Exception:
        logger.exception("session_type parse failed timestamp=%s", timestamp_str)
        return "unknown"


async def get_stock_quote(ticker: str) -> str:
    """Return a formatted real-time quote for a single ticker.

    Args:
        ticker: Stock symbol (e.g. 'AAPL', 'MSFT', 'SPY').
    """
    try:
        quote = await tradier.get_quote(ticker)
    except Exception:
        logger.exception("get_stock_quote raised ticker=%s", ticker)
        return f"Error fetching quote for {ticker}: internal exception"

    if not quote:
        return f"Quote not available for {ticker} (symbol unknown or upstream error)"

    session = _get_session_type(quote.get("t", ""))
    spread = quote["ap"] - quote["bp"]
    return f"""**{ticker.upper()} Quote**
Bid: ${quote["bp"]:.2f} x {quote["bs"]}
Ask: ${quote["ap"]:.2f} x {quote["as"]}
Spread: ${spread:.2f}
Last: ${quote["last"]:.2f}
Time: {quote["t"]}
Feed: TRADIER | Session: {session}"""


async def analyze_strat_patterns(
    ticker: str,
    timeframe: str = "1Day",
    days_back: int = 10,
) -> str:
    """Analyze a single stock for STRAT patterns with detailed bar
    classification.

    Args:
        ticker: Stock symbol.
        timeframe: Bar timeframe ('1Day', '1Week', '1Month', '1Hour', '15Min').
        days_back: Number of calendar days of history to fetch.
    """
    logger.info(
        "analyze_strat_patterns ticker=%s timeframe=%s days_back=%d",
        ticker,
        timeframe,
        days_back,
    )

    try:
        bars = await tradier.get_bars_recent(ticker, days_back=days_back, timeframe=timeframe)
    except Exception:
        logger.exception(
            "analyze_strat_patterns fetch failed ticker=%s timeframe=%s",
            ticker,
            timeframe,
        )
        return f"Error fetching data for {ticker}: internal exception"

    if not bars:
        logger.warning(
            "analyze_strat_patterns empty bars ticker=%s timeframe=%s",
            ticker,
            timeframe,
        )
        return f"No data available for {ticker}"

    try:
        patterns = STRATDetector.scan_for_patterns(bars, timeframe)
        current_price = bars[-1]["c"]
        metrics = STRATDetector.get_stock_metrics(ticker, bars)
    except Exception:
        logger.exception(
            "analyze_strat_patterns detector failed ticker=%s timeframe=%s",
            ticker,
            timeframe,
        )
        return f"Error analyzing {ticker}: detector exception"

    if not patterns:
        return (
            f"**{ticker}** - ${current_price:.2f}\n"
            f"Metrics: {metrics}\n"
            f"No STRAT patterns detected in last {days_back} bars"
        )

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

    classified_bars = STRATDetector.classify_bars(bars, timeframe)[-5:]
    report += "**Recent Bar Sequence:**\n"
    for bar in classified_bars:
        bar_date = bar.timestamp.split("T")[0]
        forming_str = " (forming)" if bar.is_forming else ""
        report += (
            f"  {bar_date}: Type {bar.bar_type}{forming_str} "
            f"(H:${bar.high:.2f} L:${bar.low:.2f} C:${bar.close:.2f})\n"
        )
    return report


async def analyze_tfc(
    ticker: str,
    include_monthly: bool = True,
    include_weekly: bool = True,
) -> str:
    """Compute Timeframe Continuity (TFC) across multiple timeframes."""
    logger.info("analyze_tfc ticker=%s", ticker)

    timeframe_data: dict = {}
    try:
        if include_monthly:
            timeframe_data["monthly"] = await tradier.get_bars_recent(
                ticker, days_back=365, timeframe="1Month"
            )
        if include_weekly:
            timeframe_data["weekly"] = await tradier.get_bars_recent(
                ticker, days_back=180, timeframe="1Week"
            )
        timeframe_data["daily"] = await tradier.get_bars_recent(
            ticker, days_back=30, timeframe="1Day"
        )
        timeframe_data["60min"] = await tradier.get_bars_recent(
            ticker, days_back=10, timeframe="1Hour"
        )
        timeframe_data["15min"] = await tradier.get_bars_recent(
            ticker, days_back=5, timeframe="15Min"
        )
    except Exception:
        logger.exception("analyze_tfc fetch failed ticker=%s", ticker)
        return f"Error fetching TFC data for {ticker}: internal exception"

    try:
        tfc = STRATDetector.calculate_tfc_score(timeframe_data)
        metrics = None
        if timeframe_data.get("daily"):
            metrics = STRATDetector.get_stock_metrics(ticker, timeframe_data["daily"])
        report = format_tfc_report(ticker, tfc, metrics)
    except Exception:
        logger.exception("analyze_tfc detector failed ticker=%s", ticker)
        return f"Error analyzing TFC for {ticker}: detector exception"

    report += "\n**Pattern Details:**\n"
    tf_mapping = {
        "monthly": ("Monthly", "1Month"),
        "weekly": ("Weekly", "1Week"),
        "daily": ("Daily", "1Day"),
        "60min": ("60min", "1Hour"),
        "15min": ("15min", "15Min"),
    }
    for tf_key, (tf_name, tf_str) in tf_mapping.items():
        bars = timeframe_data.get(tf_key, [])
        if bars:
            patterns = STRATDetector.scan_for_patterns(bars, tf_str)
            if patterns:
                top_pattern = patterns[0]
                direction = "[BULL]" if top_pattern.direction == "bullish" else "[BEAR]"
                report += (
                    f"  {direction} {tf_name}: {top_pattern.pattern_type} "
                    f"({top_pattern.confidence})\n"
                )
            else:
                report += f"  [NONE] {tf_name}: No pattern\n"
        else:
            report += f"  [----] {tf_name}: No data\n"

    report += "\n**Contextual TFC (timeframe-appropriate scoring):**\n"
    context_timeframes = {"1Hour": "Hourly", "1Day": "Daily", "1Week": "Weekly"}
    for ctx_tf, ctx_name in context_timeframes.items():
        ctx = STRATDetector.get_contextual_tfc(tfc, ctx_tf)
        pass_mark = "PASS" if ctx["passes"] else "FAIL"
        report += (
            f"  {ctx_name} patterns: {ctx['effective_score']}/{ctx['max_possible']} "
            f"({ctx['effective_quality']}) [{pass_mark}]\n"
        )
        report += (
            f"    Checks: {', '.join(ctx['relevant_timeframes'])} (need {ctx['min_required']})\n"
        )
    return report


async def scan_sector_for_strat(
    sector: str,
    top_n: int = 20,
    pattern_filter: str | None = None,
    min_atr: float = 0.0,
    min_atr_percent: float = 0.0,
    min_dollar_volume: float = 0.0,
) -> str:
    """Scan sector stocks for STRAT patterns with ATR/volume filtering."""
    sector_tickers = {
        "technology": [
            "AAPL",
            "MSFT",
            "NVDA",
            "GOOGL",
            "META",
            "TSLA",
            "AVGO",
            "ORCL",
            "AMD",
            "CRM",
            "ADBE",
            "NFLX",
            "INTC",
            "CSCO",
            "ACN",
            "IBM",
            "NOW",
            "QCOM",
            "TXN",
            "INTU",
            "AMAT",
            "MU",
            "LRCX",
            "KLAC",
            "SNPS",
            "CDNS",
            "MCHP",
            "FTNT",
            "PANW",
            "CRWD",
        ],
        "healthcare": [
            "UNH",
            "JNJ",
            "LLY",
            "ABBV",
            "MRK",
            "TMO",
            "ABT",
            "DHR",
            "PFE",
            "BMY",
            "AMGN",
            "CVS",
            "MDT",
            "GILD",
            "CI",
            "REGN",
            "SYK",
            "VRTX",
            "ZTS",
            "HUM",
            "BSX",
            "ELV",
            "ISRG",
            "MCK",
            "CVS",
            "HCA",
            "COR",
            "EW",
            "A",
            "IQV",
        ],
        "financials": [
            "JPM",
            "BAC",
            "WFC",
            "GS",
            "MS",
            "C",
            "BLK",
            "SCHW",
            "CB",
            "AXP",
            "PNC",
            "USB",
            "TFC",
            "COF",
            "BK",
            "AIG",
            "MET",
            "AFL",
            "PRU",
            "ALL",
            "CME",
            "SPGI",
            "ICE",
            "MCO",
            "AON",
            "MMC",
            "TRV",
            "PGR",
            "AJG",
            "WRB",
        ],
        "energy": [
            "XOM",
            "CVX",
            "COP",
            "SLB",
            "EOG",
            "MPC",
            "PSX",
            "VLO",
            "OXY",
            "WMB",
            "HAL",
            "DVN",
            "HES",
            "FANG",
            "BKR",
            "KMI",
            "MRO",
            "APA",
            "EQT",
            "CTRA",
            "OKE",
            "LNG",
            "TRGP",
            "EPD",
            "ET",
            "EXE",
            "XEC",
            "CVE",
            "CNQ",
            "SU",
        ],
        "consumer": [
            "AMZN",
            "TSLA",
            "HD",
            "MCD",
            "NKE",
            "SBUX",
            "TGT",
            "LOW",
            "TJX",
            "BKNG",
            "CMG",
            "MAR",
            "ORLY",
            "AZO",
            "YUM",
            "ROST",
            "DHI",
            "LEN",
            "F",
            "GM",
            "EBAY",
            "COST",
            "WMT",
            "PG",
            "KO",
            "PEP",
            "MDLZ",
            "CL",
            "EL",
            "CLX",
        ],
        "industrials": [
            "CAT",
            "GE",
            "RTX",
            "UNP",
            "BA",
            "HON",
            "LMT",
            "DE",
            "UPS",
            "ADP",
            "MMM",
            "GD",
            "ETN",
            "ITW",
            "EMR",
            "PCAR",
            "NOC",
            "FDX",
            "CSX",
            "WM",
            "NSC",
            "TT",
            "PH",
            "JCI",
            "CARR",
            "OTIS",
            "ROK",
            "AME",
            "FAST",
            "PWR",
        ],
        "materials": [
            "LIN",
            "APD",
            "SHW",
            "FCX",
            "ECL",
            "NEM",
            "CTVA",
            "DD",
            "NUE",
            "VMC",
            "MLM",
            "PPG",
            "ALB",
            "CF",
            "MOS",
            "FMC",
            "IFF",
            "EMN",
            "CE",
            "AVY",
        ],
        "utilities": [
            "NEE",
            "DUK",
            "SO",
            "D",
            "AEP",
            "EXC",
            "SRE",
            "XEL",
            "ED",
            "PEG",
            "WEC",
            "ES",
            "AWK",
            "DTE",
            "EIX",
            "FE",
            "ETR",
            "PPL",
            "AEE",
            "CMS",
        ],
        "real_estate": [
            "PLD",
            "AMT",
            "CCI",
            "EQIX",
            "PSA",
            "WELL",
            "DLR",
            "O",
            "SBAC",
            "AVB",
            "EQR",
            "SPG",
            "VTR",
            "ARE",
            "INVH",
            "MAA",
            "ESS",
            "KIM",
            "REG",
            "BXP",
        ],
        "communications": [
            "GOOGL",
            "META",
            "NFLX",
            "DIS",
            "CMCSA",
            "T",
            "VZ",
            "TMUS",
            "CHTR",
            "EA",
            "TTWO",
            "OMC",
            "IPG",
            "FOXA",
            "PARA",
            "WBD",
            "LYV",
            "NWSA",
            "MTCH",
            "PINS",
        ],
    }

    tickers = sector_tickers.get(sector.lower(), sector_tickers["technology"])[: min(top_n, 100)]
    results: list = []
    filtered_count = 0
    completed = 0
    total = len(tickers)

    for ticker in tickers:
        try:
            bars = await tradier.get_bars_recent(ticker, days_back=30, timeframe="1Day")
        except Exception:
            logger.exception("scan_sector_for_strat fetch failed ticker=%s", ticker)
            completed += 1
            continue

        if not bars:
            completed += 1
            continue

        metrics = STRATDetector.get_stock_metrics(ticker, bars)
        if not metrics.passes_filter(min_atr, min_atr_percent, min_dollar_volume):
            filtered_count += 1
            completed += 1
            continue

        patterns = STRATDetector.scan_for_patterns(bars)
        if patterns:
            if pattern_filter:
                patterns = [p for p in patterns if pattern_filter.lower() in p.pattern_type.lower()]
            if patterns:
                current_price = bars[-1]["c"]
                results.append(
                    {
                        "ticker": ticker,
                        "price": current_price,
                        "patterns": patterns,
                        "metrics": metrics,
                    }
                )

        completed += 1
        if completed % 10 == 0:
            logger.info("scan_sector_for_strat progress=%d/%d", completed, total)

    if not results:
        filter_text = f" matching '{pattern_filter}'" if pattern_filter else ""
        filter_info = ""
        if min_atr > 0 or min_atr_percent > 0 or min_dollar_volume > 0:
            filter_info = f" ({filtered_count} filtered by ATR/volume)"
        return f"No STRAT patterns{filter_text} found in {sector} sector stocks{filter_info}"

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
    min_dollar_volume: float = 0.0,
) -> str:
    """Scan top holdings of an ETF for STRAT patterns with ATR/volume filtering."""
    etf_holdings = {
        "SPY": [
            "AAPL",
            "MSFT",
            "NVDA",
            "AMZN",
            "GOOGL",
            "META",
            "BRK.B",
            "AVGO",
            "LLY",
            "TSLA",
            "JPM",
            "WMT",
            "V",
            "XOM",
            "UNH",
            "MA",
            "PG",
            "COST",
            "JNJ",
            "HD",
        ],
        "QQQ": [
            "AAPL",
            "MSFT",
            "NVDA",
            "AMZN",
            "META",
            "AVGO",
            "TSLA",
            "GOOGL",
            "COST",
            "NFLX",
            "AMD",
            "PEP",
            "ADBE",
            "CSCO",
            "TMUS",
            "INTC",
            "CMCSA",
            "TXN",
            "INTU",
            "AMGN",
        ],
        "IWM": [
            "RELY",
            "GKOS",
            "ALKT",
            "EXLS",
            "NOVT",
            "WTFC",
            "NXST",
            "UFPI",
            "STRL",
            "SHOO",
            "CASY",
            "AXON",
            "ESNT",
            "CRVL",
            "TGTX",
            "SAIA",
            "BOOT",
            "ATKR",
            "ONTO",
            "MTH",
        ],
        "XLK": [
            "AAPL",
            "MSFT",
            "NVDA",
            "AVGO",
            "CRM",
            "ORCL",
            "AMD",
            "CSCO",
            "ACN",
            "ADBE",
            "IBM",
            "INTC",
            "QCOM",
            "NOW",
            "TXN",
            "INTU",
            "AMAT",
            "MU",
            "LRCX",
            "KLAC",
        ],
        "XLF": [
            "JPM",
            "BAC",
            "WFC",
            "MS",
            "GS",
            "BLK",
            "C",
            "SCHW",
            "CB",
            "AXP",
            "PNC",
            "USB",
            "TFC",
            "AIG",
            "COF",
            "AFL",
            "MET",
            "PRU",
            "ALL",
            "BK",
        ],
        "XLE": [
            "XOM",
            "CVX",
            "COP",
            "SLB",
            "EOG",
            "MPC",
            "PSX",
            "VLO",
            "OXY",
            "HAL",
            "WMB",
            "BKR",
            "FANG",
            "DVN",
            "HES",
            "KMI",
            "MRO",
            "CTRA",
            "APA",
            "EQT",
        ],
        "XLV": [
            "UNH",
            "LLY",
            "JNJ",
            "ABBV",
            "MRK",
            "TMO",
            "ABT",
            "DHR",
            "PFE",
            "BMY",
            "AMGN",
            "CVS",
            "MDT",
            "GILD",
            "CI",
            "REGN",
            "VRTX",
            "SYK",
            "ZTS",
            "HUM",
        ],
    }

    holdings = etf_holdings.get(etf.upper(), etf_holdings["SPY"])[:top_n]
    results: list = []
    filtered_count = 0
    completed = 0
    total = len(holdings)

    for ticker in holdings:
        try:
            bars = await tradier.get_bars_recent(ticker, days_back=30, timeframe="1Day")
        except Exception:
            logger.exception("scan_etf_holdings_strat fetch failed ticker=%s", ticker)
            completed += 1
            continue

        if not bars:
            completed += 1
            continue

        metrics = STRATDetector.get_stock_metrics(ticker, bars)
        if not metrics.passes_filter(min_atr, min_atr_percent, min_dollar_volume):
            filtered_count += 1
            completed += 1
            continue

        patterns = STRATDetector.scan_for_patterns(bars)
        if patterns:
            current_price = bars[-1]["c"]
            results.append(
                {
                    "ticker": ticker,
                    "price": current_price,
                    "patterns": patterns,
                    "metrics": metrics,
                }
            )

        completed += 1
        if completed % 10 == 0:
            logger.info("scan_etf_holdings_strat progress=%d/%d", completed, total)

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
    tickers: list[str],
    min_score: int = 3,
    direction: str = "bullish",
    include_monthly: bool = True,
    min_atr: float = 0.0,
    min_atr_percent: float = 0.0,
    min_dollar_volume: float = 0.0,
) -> str:
    """Scan multiple stocks for Timeframe Continuity alignment."""
    logger.info(
        "scan_for_tfc_alignment count=%d min_score=%d direction=%s",
        len(tickers),
        min_score,
        direction,
    )

    results: list = []
    filtered_count = 0

    for ticker in tickers:
        try:
            timeframe_data: dict = {}
            if include_monthly:
                timeframe_data["monthly"] = await tradier.get_bars_recent(
                    ticker, days_back=365, timeframe="1Month"
                )
            timeframe_data["weekly"] = await tradier.get_bars_recent(
                ticker, days_back=180, timeframe="1Week"
            )
            daily_bars = await tradier.get_bars_recent(ticker, days_back=30, timeframe="1Day")
            timeframe_data["daily"] = daily_bars

            if not daily_bars:
                continue

            metrics = STRATDetector.get_stock_metrics(ticker, daily_bars)
            if not metrics.passes_filter(min_atr, min_atr_percent, min_dollar_volume):
                filtered_count += 1
                continue

            timeframe_data["60min"] = await tradier.get_bars_recent(
                ticker, days_back=10, timeframe="1Hour"
            )
            timeframe_data["15min"] = await tradier.get_bars_recent(
                ticker, days_back=5, timeframe="15Min"
            )

            tfc = STRATDetector.calculate_tfc_score(timeframe_data)
            if tfc.score >= min_score:
                if direction == "any" or tfc.dominant_bias == direction:
                    results.append({"ticker": ticker, "tfc": tfc, "metrics": metrics})

        except Exception:
            logger.exception("scan_for_tfc_alignment ticker=%s failed", ticker)
            continue

    if not results:
        return f"No stocks found with TFC score >= {min_score} ({direction})"

    results.sort(key=lambda x: (x["tfc"].score, x["metrics"].atr_percent), reverse=True)
    output = (
        f"**TFC Alignment Scan** - {len(results)} stocks with {min_score}/5+ "
        f"{direction} alignment\n"
    )
    if filtered_count > 0:
        output += f"({filtered_count} filtered by ATR/volume)\n"
    output += "\n"
    for i, result in enumerate(results, 1):
        tfc = result["tfc"]
        metrics = result["metrics"]
        ticker = result["ticker"]
        bias_marker = "[BULL]" if tfc.dominant_bias == "bullish" else "[BEAR]"
        output += f"{i}. {bias_marker} **{ticker}** - TFC {tfc.score}/5 ({tfc.quality})\n"
        output += f"   Aligned: {', '.join(tfc.aligned_timeframes)}\n"
        output += f"   Metrics: {metrics}\n\n"
    return output


async def get_multiple_quotes(tickers: list[str]) -> str:
    """Get quotes for multiple stocks in a single batched API call."""
    if len(tickers) > 50:
        return "Error: Maximum 50 tickers per request"

    try:
        quotes = await tradier.get_multiple_quotes(tickers)
    except Exception:
        logger.exception("get_multiple_quotes raised count=%d", len(tickers))
        return "Error fetching quotes: internal exception"

    results = []
    for ticker in tickers:
        sym = ticker.upper()
        quote = quotes.get(sym)
        if quote:
            results.append(f"{sym}: ${quote['ap']:.2f} (Bid: ${quote['bp']:.2f})")
        else:
            results.append(f"{sym}: No data")
    return "\n".join(results)
