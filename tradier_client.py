"""
Tradier API client wrapper with rate limiting and response normalization.

Provides a thin async client over the Tradier Market Data REST API. The client
normalizes Tradier's idiosyncratic response shapes into the internal bar/quote
dict shape that the STRAT detector already expects (keys: t, o, h, l, c, v for
bars; bp, bs, ap, as, t for quotes). This keeps strat_detector.py untouched.

Endpoints used:
    GET  /v1/markets/quotes        (small batches via querystring)
    POST /v1/markets/quotes        (large batches via form-encoded body)
    GET  /v1/markets/history       (daily / weekly / monthly bars)
    GET  /v1/markets/timesales     (intraday 1min / 5min / 15min)
    GET  /v1/markets/clock         (market session state, optional)

Rate limiting:
    Tradier production caps endpoints at 60-120 requests per rolling minute.
    The shared rate_limiter throttles to RATE_LIMIT_PER_MINUTE (default 100)
    as a safety margin.

Logging:
    Every outbound call logs INFO with endpoint, latency_ms, status_code.
    Every error path calls logger.exception() before returning a user-facing
    sentinel value (None / empty list). This is the explicit fix for the
    invisible-failure mode that motivated this migration.
"""

from __future__ import annotations

import logging
import time as _time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytz
from config import settings
from rate_limiter import api_rate_limiter

logger = logging.getLogger(__name__)


# --- Timeframe helpers -------------------------------------------------------

# Mapping from the existing Alpaca-style timeframe strings (used by the
# scanner) to Tradier's history "interval" parameter.
HISTORY_INTERVAL_MAP = {
    "1Day": "daily",
    "1Week": "weekly",
    "1Month": "monthly",
}

# Mapping from the existing Alpaca-style intraday timeframe strings to
# Tradier's timesales "interval" parameter.
TIMESALES_INTERVAL_MAP = {
    "1Min": "1min",
    "5Min": "5min",
    "15Min": "15min",
    "1Hour": "15min",  # Tradier timesales has no 1H bar; aggregate from 15min
}

# Number of native bars to combine into one returned bar (only relevant for
# 1Hour aggregation from 15min bars).
HOURLY_AGG_FACTOR = 4

# Eastern timezone — Tradier returns date strings, we normalize bar timestamps
# to the US session close (16:00 ET) in UTC for daily / weekly / monthly so the
# downstream is_bar_forming logic in strat_detector continues to work.
_ET = pytz.timezone("America/New_York")
_SESSION_CLOSE = (16, 0)

# US regular-session open in ET. Used by the 1Hour aggregator to align buckets
# to 9:30 / 10:30 / 11:30 / ... rather than UTC midnight, which matches how
# TradingView presents hourly bars.
_SESSION_OPEN_HOUR = 9
_SESSION_OPEN_MINUTE = 30


def _to_tradier_symbol(symbol: str) -> str:
    """Translate the canonical scanner symbol form to Tradier's wire form.
    Tradier uses '/' to separate class shares (BRK.B is written BRK/B). Idempotent
    on symbols without a dot."""
    return symbol.replace(".", "/")


def _from_tradier_symbol(symbol: str) -> str:
    """Inverse of _to_tradier_symbol — translate Tradier's wire form back to the
    scanner's canonical form so caller-side keys (ETF holding lists, etc.) match."""
    return symbol.replace("/", ".")


def _date_to_session_close_utc(date_str: str) -> str:
    """Normalize a YYYY-MM-DD Tradier history date to a UTC ISO timestamp at
    the 16:00 ET session close. Returns the original string if parsing fails;
    that path is unreachable in normal Tradier responses but defensive."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        d = _ET.localize(d.replace(hour=_SESSION_CLOSE[0], minute=_SESSION_CLOSE[1]))
        return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return date_str


def _normalize_intraday_timestamp(ts_str: str) -> str:
    """Tradier timesales returns intraday timestamps in ET, typically as
    'YYYY-MM-DDTHH:MM:SS' (ISO 8601) and occasionally as 'YYYY-MM-DD HH:MM'
    on older response shapes. fromisoformat handles every separator + the
    optional seconds suffix since Python 3.11. Convert to UTC ISO with Z."""
    try:
        dt = datetime.fromisoformat(ts_str)
    except ValueError:
        return ts_str
    if dt.tzinfo is None:
        dt = _ET.localize(dt)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _date_param(dt: datetime, granular: bool = False) -> str:
    """Tradier accepts YYYY-MM-DD for history; YYYY-MM-DD HH:MM for timesales.

    Tradier interprets both date forms as US/Eastern local time. Any tz-aware
    datetime (typically UTC from get_bars_recent) must be converted to ET before
    formatting, otherwise the request queries a wall-clock-shifted window and
    silently misses bars at session boundaries."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(_ET)
    if granular:
        return dt.strftime("%Y-%m-%d %H:%M")
    return dt.strftime("%Y-%m-%d")


# --- Client ------------------------------------------------------------------


class TradierError(Exception):
    """Raised for Tradier API responses that signal an unrecoverable error
    (auth failure, malformed response, fault payload)."""


class TradierClient:
    """Async REST client for Tradier Market Data API.

    Thread-safety: instances are safe to share across asyncio tasks because
    all state (rate limiter, semaphore) lives in the module-level objects.
    """

    def __init__(self) -> None:
        # base_url and token derive from a single switch (TRADIER_USE_SANDBOX) so
        # they cannot drift; previously they were two independent settings, which
        # let a sandbox token be sent to the production endpoint and 401.
        if settings.TRADIER_USE_SANDBOX:
            self.base_url = "https://sandbox.tradier.com/v1"
            token = settings.TRADIER_SANDBOX_TOKEN or settings.TRADIER_API_TOKEN
        else:
            self.base_url = "https://api.tradier.com/v1"
            token = settings.TRADIER_API_TOKEN
        if not token:
            raise RuntimeError(
                "TRADIER_API_TOKEN (or TRADIER_SANDBOX_TOKEN when "
                "TRADIER_USE_SANDBOX=true) must be set"
            )
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    # -- HTTP plumbing --------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        timeout: float = 15.0,
        symbol_log: str | None = None,
    ) -> dict[str, Any] | None:
        """Execute a single API call through the rate limiter. Returns the
        parsed JSON body or None on terminal error. All errors are logged
        with structured fields before the None return."""
        url = f"{self.base_url}{path}"
        started = _time.monotonic()
        async with httpx.AsyncClient() as client:
            try:
                response = await api_rate_limiter.make_request(
                    client,
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=self.headers,
                    timeout=timeout,
                )
            except Exception:
                logger.exception(
                    "tradier request raised (endpoint=%s symbol=%s)",
                    path,
                    symbol_log,
                )
                return None

        latency_ms = int((_time.monotonic() - started) * 1000)

        if response is None:
            logger.error(
                "tradier request returned no response "
                "(endpoint=%s symbol=%s latency_ms=%d error_type=no_response)",
                path,
                symbol_log,
                latency_ms,
            )
            return None

        request_id = response.headers.get("x-tradier-request-id") or response.headers.get(
            "x-request-id"
        )

        if response.status_code != 200:
            logger.error(
                "tradier non-200 (endpoint=%s symbol=%s status_code=%d "
                "latency_ms=%d request_id=%s body=%s)",
                path,
                symbol_log,
                response.status_code,
                latency_ms,
                request_id,
                response.text[:300],
            )
            return None

        try:
            body = response.json()
        except Exception:
            logger.exception(
                "tradier json parse failed (endpoint=%s symbol=%s status_code=%d "
                "latency_ms=%d body=%s)",
                path,
                symbol_log,
                response.status_code,
                latency_ms,
                response.text[:300],
            )
            return None

        # Tradier returns a 200 with a "fault" body for auth / quota failures.
        if isinstance(body, dict) and "fault" in body:
            fault = body.get("fault") or {}
            logger.error(
                "tradier fault response (endpoint=%s symbol=%s status_code=%d "
                "latency_ms=%d request_id=%s faultstring=%s)",
                path,
                symbol_log,
                response.status_code,
                latency_ms,
                request_id,
                fault.get("faultstring"),
            )
            return None

        logger.info(
            "tradier ok (endpoint=%s symbol=%s status_code=%d latency_ms=%d request_id=%s)",
            path,
            symbol_log,
            response.status_code,
            latency_ms,
            request_id,
        )
        return body

    # -- Quote normalization --------------------------------------------------

    @staticmethod
    def _normalize_quote(tradier_quote: dict[str, Any]) -> dict[str, Any]:
        """Convert a Tradier quote dict into the {bp, bs, ap, as, t} shape the
        scanner's MCP tools expect.

        Tradier fields used:
            bid, bidsize, ask, asksize, trade_date (epoch ms), last
        """
        trade_date_ms = tradier_quote.get("trade_date") or 0
        if isinstance(trade_date_ms, (int, float)) and trade_date_ms > 0:
            dt = datetime.fromtimestamp(trade_date_ms / 1000.0, tz=UTC)
            t_iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            t_iso = ""

        return {
            "bp": float(tradier_quote.get("bid") or 0.0),
            "bs": int(tradier_quote.get("bidsize") or 0),
            "ap": float(tradier_quote.get("ask") or 0.0),
            "as": int(tradier_quote.get("asksize") or 0),
            "t": t_iso,
            "last": float(tradier_quote.get("last") or 0.0),
            "symbol": _from_tradier_symbol(tradier_quote.get("symbol", "")),
        }

    @staticmethod
    def _extract_quotes(body: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract the list of matched quote dicts from a Tradier quotes
        response, handling all three response shapes: single object, list,
        or unmatched-only."""
        quotes_root = (body or {}).get("quotes") or {}
        if not isinstance(quotes_root, dict):
            return []
        raw = quotes_root.get("quote")
        if raw is None:
            return []  # unmatched_symbols only / empty
        if isinstance(raw, list):
            return raw
        return [raw]

    @staticmethod
    def _extract_unmatched(body: dict[str, Any]) -> list[str]:
        """Extract the list of unmatched symbols. The "symbol" field may be a
        string (single) or a list (multiple)."""
        quotes_root = (body or {}).get("quotes") or {}
        if not isinstance(quotes_root, dict):
            return []
        unmatched = quotes_root.get("unmatched_symbols") or {}
        if not isinstance(unmatched, dict):
            return []
        sym = unmatched.get("symbol")
        if sym is None:
            return []
        if isinstance(sym, list):
            return [str(s) for s in sym]
        return [str(sym)]

    # -- Public: quotes -------------------------------------------------------

    async def get_quote(self, ticker: str) -> dict[str, Any] | None:
        """Fetch a single quote. Returns the normalized quote dict (with bp,
        ap, etc.) or None when the symbol is unknown / request failed."""
        symbol = ticker.upper()
        wire = _to_tradier_symbol(symbol)
        body = await self._request(
            "GET",
            "/markets/quotes",
            params={"symbols": wire, "greeks": "false"},
            symbol_log=symbol,
        )
        if body is None:
            return None
        quotes = self._extract_quotes(body)
        if not quotes:
            unmatched = self._extract_unmatched(body)
            unmatched_canonical = [_from_tradier_symbol(u) for u in unmatched]
            if symbol in unmatched_canonical:
                logger.warning(
                    "tradier symbol not found (endpoint=/markets/quotes symbol=%s)",
                    symbol,
                )
            return None
        return self._normalize_quote(quotes[0])

    async def get_multiple_quotes(self, tickers: list[str]) -> dict[str, dict[str, Any] | None]:
        """Batch-fetch quotes for many tickers in a single API call. Uses
        POST for >10 symbols (form-encoded) per the spec's rate-budget note.
        Returns a {symbol: quote_or_None} map preserving input case-folded
        keys (uppercased canonical form, e.g. BRK.B not BRK/B)."""
        symbols = [t.upper() for t in tickers]
        if not symbols:
            return {}

        wire_symbols = [_to_tradier_symbol(s) for s in symbols]
        symbols_param = ",".join(wire_symbols)
        if len(symbols) > 10:
            body = await self._request(
                "POST",
                "/markets/quotes",
                data={"symbols": symbols_param, "greeks": "false"},
                symbol_log=f"batch[{len(symbols)}]",
            )
        else:
            body = await self._request(
                "GET",
                "/markets/quotes",
                params={"symbols": symbols_param, "greeks": "false"},
                symbol_log=f"batch[{len(symbols)}]",
            )

        result: dict[str, dict[str, Any] | None] = {s: None for s in symbols}
        if body is None:
            return result

        for q in self._extract_quotes(body):
            wire_sym = (q.get("symbol") or "").upper()
            canonical_sym = _from_tradier_symbol(wire_sym)
            if canonical_sym in result:
                result[canonical_sym] = self._normalize_quote(q)
        return result

    # -- Public: history (daily / weekly / monthly) ---------------------------

    @staticmethod
    def _normalize_history_day(day: dict[str, Any]) -> dict[str, Any]:
        """Convert a Tradier history "day" entry to the scanner's internal
        bar shape {t, o, h, l, c, v}."""
        return {
            "t": _date_to_session_close_utc(str(day.get("date", ""))),
            "o": float(day.get("open") or 0.0),
            "h": float(day.get("high") or 0.0),
            "l": float(day.get("low") or 0.0),
            "c": float(day.get("close") or 0.0),
            "v": int(day.get("volume") or 0),
        }

    @staticmethod
    def _extract_history_days(body: dict[str, Any]) -> list[dict[str, Any]]:
        history_root = (body or {}).get("history")
        # Tradier returns "history": null on no-data
        if not history_root or not isinstance(history_root, dict):
            return []
        days = history_root.get("day")
        if days is None:
            return []
        if isinstance(days, list):
            return days
        return [days]

    async def get_history(
        self,
        ticker: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily / weekly / monthly bars for a ticker.

        Args:
            ticker: Symbol.
            interval: One of "daily", "weekly", "monthly".
            start, end: Inclusive date range.

        Returns:
            List of normalized bar dicts (oldest to newest). Empty list on
            error / no data.
        """
        symbol = ticker.upper()
        body = await self._request(
            "GET",
            "/markets/history",
            params={
                "symbol": _to_tradier_symbol(symbol),
                "interval": interval,
                "start": _date_param(start),
                "end": _date_param(end),
            },
            symbol_log=symbol,
        )
        if body is None:
            return []
        days = self._extract_history_days(body)
        return [self._normalize_history_day(d) for d in days]

    # -- Public: timesales (intraday) -----------------------------------------

    @staticmethod
    def _normalize_timesales_bar(bar: dict[str, Any]) -> dict[str, Any]:
        ts_raw = str(bar.get("time", ""))
        return {
            "t": _normalize_intraday_timestamp(ts_raw),
            "o": float(bar.get("open") or 0.0),
            "h": float(bar.get("high") or 0.0),
            "l": float(bar.get("low") or 0.0),
            "c": float(bar.get("close") or 0.0),
            "v": int(bar.get("volume") or 0),
        }

    @staticmethod
    def _extract_timesales(body: dict[str, Any]) -> list[dict[str, Any]]:
        series = (body or {}).get("series")
        if not series or not isinstance(series, dict):
            return []
        data = series.get("data")
        if data is None:
            return []
        if isinstance(data, list):
            return data
        return [data]

    @staticmethod
    def _aggregate_to_hourly(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Aggregate 15min bars into 1H buckets aligned to the 9:30 ET session
        open. Buckets cover 9:30-10:30, 10:30-11:30, ..., 14:30-15:30 ET, plus
        a partial 15:30-16:00 ET bucket containing the last two 15min bars of
        the regular session. Bucket keys are the bucket-open time as a UTC ISO
        string. Bars outside regular hours (only possible if the caller
        bypasses session_filter=open) are bucketed by their containing
        :30-aligned hour and may produce unusual keys.

        Each bucket emits O=first.O, H=max, L=min, C=last.C, V=sum."""
        if not bars:
            return []

        from collections import OrderedDict

        buckets: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        for b in bars:
            ts = b["t"]
            try:
                dt_utc = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
                dt_et = dt_utc.astimezone(_ET)
            except Exception:
                # Defensive: if a timestamp ever fails to parse, key by its
                # raw string so the bar is not silently dropped.
                buckets.setdefault(ts, []).append(b)
                continue

            # Compute the open-aligned bucket. Each bucket opens on a :30
            # minute mark on a one-hour stride from 9:30 ET. The number of
            # minutes elapsed since the most recent bucket open is therefore
            # ((minutes-since-9:30-ET) mod 60). Subtracting that gets us back
            # to the bucket-open instant.
            minutes_since_open = (
                (dt_et.hour - _SESSION_OPEN_HOUR) * 60
                + (dt_et.minute - _SESSION_OPEN_MINUTE)
            )
            minutes_into_bucket = minutes_since_open % 60
            bucket_open_et = (
                dt_et - timedelta(minutes=minutes_into_bucket)
            ).replace(second=0, microsecond=0)
            bucket_key = bucket_open_et.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            buckets.setdefault(bucket_key, []).append(b)

        agg: list[dict[str, Any]] = []
        for bucket_key, group in buckets.items():
            if not group:
                continue
            agg.append(
                {
                    "t": bucket_key,
                    "o": group[0]["o"],
                    "h": max(g["h"] for g in group),
                    "l": min(g["l"] for g in group),
                    "c": group[-1]["c"],
                    "v": sum(g["v"] for g in group),
                }
            )
        return agg

    async def get_timesales(
        self,
        ticker: str,
        interval: str,
        start: datetime,
        end: datetime,
        aggregate_to_hourly: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch intraday bars. interval is the Tradier-native value
        ("1min" / "5min" / "15min"). If aggregate_to_hourly is True the 15min
        bars are rolled up to hourly buckets.
        """
        symbol = ticker.upper()
        body = await self._request(
            "GET",
            "/markets/timesales",
            params={
                "symbol": _to_tradier_symbol(symbol),
                "interval": interval,
                "start": _date_param(start, granular=True),
                "end": _date_param(end, granular=True),
                # Regular session only — including pre/post-market widens OHLCV
                # ranges and silently flips STRAT bar classifications relative
                # to what TradingView shows.
                "session_filter": "open",
            },
            symbol_log=symbol,
            timeout=25.0,
        )
        if body is None:
            return []
        raw_bars = self._extract_timesales(body)
        normalized = [self._normalize_timesales_bar(b) for b in raw_bars]
        if aggregate_to_hourly:
            return self._aggregate_to_hourly(normalized)
        return normalized

    # -- Public: bars (Alpaca-compat convenience methods) ---------------------

    async def get_bars(
        self,
        ticker: str,
        start: str,
        end: str,
        timeframe: str = "1Day",
    ) -> list[dict[str, Any]]:
        """Drop-in replacement for the AlpacaClient.get_bars surface used by
        mcp_tools. Accepts the scanner's Alpaca-style timeframe strings
        ("1Day", "1Week", "1Month", "1Hour", "15Min", "5Min", "1Min") and an
        ISO RFC3339 start/end. Routes to /markets/history for >=daily and to
        /markets/timesales for intraday.
        """
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except Exception:
            logger.exception(
                "tradier get_bars failed to parse start/end (symbol=%s start=%s end=%s)",
                ticker,
                start,
                end,
            )
            return []

        if timeframe in HISTORY_INTERVAL_MAP:
            return await self.get_history(
                ticker,
                HISTORY_INTERVAL_MAP[timeframe],
                start_dt,
                end_dt,
            )

        if timeframe in TIMESALES_INTERVAL_MAP:
            interval = TIMESALES_INTERVAL_MAP[timeframe]
            aggregate = timeframe == "1Hour"
            return await self.get_timesales(
                ticker, interval, start_dt, end_dt, aggregate_to_hourly=aggregate
            )

        logger.error(
            "tradier get_bars unknown timeframe (symbol=%s timeframe=%s)",
            ticker,
            timeframe,
        )
        return []

    async def get_bars_recent(
        self,
        ticker: str,
        days_back: int = 10,
        timeframe: str = "1Day",
    ) -> list[dict[str, Any]]:
        """Convenience wrapper: fetch the last N days of bars in the given
        timeframe. Mirrors AlpacaClient.get_bars_recent so the scanner does
        not need to change call sites."""
        end_dt = datetime.now(UTC)
        start_dt = end_dt - timedelta(days=days_back)
        start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return await self.get_bars(ticker, start_str, end_str, timeframe)

    # -- Public: clock --------------------------------------------------------

    async def get_clock(self) -> dict[str, Any] | None:
        """Fetch the current market clock. Returns the raw "clock" sub-dict
        from Tradier or None on error. Caller may use this to short-circuit
        scans outside market hours."""
        body = await self._request("GET", "/markets/clock")
        if body is None:
            return None
        return body.get("clock")


# Singleton — instantiation reads settings, which read env at import time. The
# auth header is rebuilt only at construction; if the token is rotated at
# runtime, restart the process.
tradier = TradierClient()
