"""
Offline tests for the Tradier response normalization layer.

These tests do NOT hit the network. They feed captured fixture payloads
through the static normalization helpers on TradierClient to confirm that
every documented Tradier response shape maps cleanly into the internal
{t, o, h, l, c, v} bar shape (or the {bp, bs, ap, as, t, last, symbol}
quote shape) that the STRAT detector consumes.

The fixtures live in tests/fixtures/tradier/. Replace them with real curl
captures (see tests/fixtures/tradier/README.md) once a live token is
available.
"""

import json
import os

import pytest
from tradier_client import TradierClient

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "tradier")


def _load(name: str) -> dict:
    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


# --- Quote normalization -----------------------------------------------------


def test_extract_quotes_single_object_shape():
    """Single-symbol response: quotes.quote is a single dict, not a list."""
    body = _load("quote_single.json")
    quotes = TradierClient._extract_quotes(body)
    assert len(quotes) == 1
    assert quotes[0]["symbol"] == "AAPL"


def test_extract_quotes_batch_array_shape():
    """Multi-symbol response: quotes.quote is a list."""
    body = _load("quote_batch.json")
    quotes = TradierClient._extract_quotes(body)
    assert len(quotes) == 3
    assert {q["symbol"] for q in quotes} == {"SPY", "QQQ", "IWM"}


def test_extract_quotes_unmatched_returns_empty():
    body = _load("quote_unmatched.json")
    quotes = TradierClient._extract_quotes(body)
    assert quotes == []
    unmatched = TradierClient._extract_unmatched(body)
    assert unmatched == ["BADTICKER123"]


def test_normalize_quote_internal_shape():
    """Normalized quote has the exact keys mcp_tools relies on."""
    body = _load("quote_single.json")
    raw = TradierClient._extract_quotes(body)[0]
    normalized = TradierClient._normalize_quote(raw)

    for key in ("bp", "bs", "ap", "as", "t", "last", "symbol"):
        assert key in normalized, f"normalized quote missing key {key!r}"

    assert normalized["bp"] == pytest.approx(308.5)
    assert normalized["ap"] == pytest.approx(308.6)
    assert normalized["bs"] == 1040
    assert normalized["as"] == 80
    assert normalized["last"] == pytest.approx(308.82)
    assert normalized["symbol"] == "AAPL"

    # trade_date 1779480000301 = 2026-05-22T20:00:00 UTC (16:00 ET session close)
    assert normalized["t"].startswith("2026-05-22T")
    assert normalized["t"].endswith("Z")


# --- History normalization ---------------------------------------------------


def test_extract_history_days_array_shape():
    body = _load("history_daily.json")
    days = TradierClient._extract_history_days(body)
    assert len(days) == 5
    assert days[0]["date"] == "2024-05-13"


def test_extract_history_days_single_object_shape():
    body = _load("history_single_day.json")
    days = TradierClient._extract_history_days(body)
    assert len(days) == 1
    assert days[0]["date"] == "2024-05-17"


def test_extract_history_days_empty():
    body = _load("history_empty.json")
    assert TradierClient._extract_history_days(body) == []


def test_normalize_history_day_internal_shape():
    """Each Tradier 'day' must map to the {t, o, h, l, c, v} bar shape with
    timestamps anchored at 16:00 ET (= 20:00 UTC during EDT) in UTC ISO."""
    body = _load("history_daily.json")
    raw = TradierClient._extract_history_days(body)[0]
    bar = TradierClient._normalize_history_day(raw)

    for key in ("t", "o", "h", "l", "c", "v"):
        assert key in bar, f"normalized bar missing key {key!r}"

    assert bar["o"] == pytest.approx(185.435)
    assert bar["h"] == pytest.approx(187.1)
    assert bar["l"] == pytest.approx(184.62)
    assert bar["c"] == pytest.approx(186.28)
    assert bar["v"] == 72044809

    # Timestamp should be UTC ISO from the 2024-05-13 16:00 ET anchor.
    # During DST that's 20:00 UTC. The exact hour can shift around DST cuts;
    # we just confirm format + the right date prefix.
    assert bar["t"].startswith("2024-05-13T")
    assert bar["t"].endswith("Z")


# --- Timesales normalization -------------------------------------------------


def test_extract_timesales_list_shape():
    body = _load("timesales_15min.json")
    bars = TradierClient._extract_timesales(body)
    assert len(bars) == 8
    # Tradier returns ISO 8601 with 'T' separator and seconds, e.g.
    # "2026-05-21T09:30:00". The normalizer (_normalize_intraday_timestamp)
    # converts to UTC ISO; extract preserves the raw shape.
    assert bars[0]["time"] == "2026-05-21T09:30:00"


def test_normalize_timesales_bar_internal_shape():
    body = _load("timesales_15min.json")
    raw = TradierClient._extract_timesales(body)[0]
    bar = TradierClient._normalize_timesales_bar(raw)

    for key in ("t", "o", "h", "l", "c", "v"):
        assert key in bar
    assert bar["o"] == pytest.approx(301.03)
    assert bar["h"] == pytest.approx(302.47)
    assert bar["l"] == pytest.approx(300.4)
    assert bar["c"] == pytest.approx(301.84)
    assert bar["v"] == 2239603
    # 2026-05-21 09:30 ET => 13:30 UTC (EDT, UTC-4)
    assert bar["t"] == "2026-05-21T13:30:00Z"


def test_hourly_aggregation_session_open_aligned():
    """8x 15min AAPL bars from 2026-05-21 09:30-11:15 ET roll up to exactly two
    1H buckets aligned to the 9:30 ET session open, not UTC hour boundaries.
    Bucket 1: 09:30-10:30 ET (4 sub-bars); Bucket 2: 10:30-11:30 ET (4 sub-bars).
    During EDT (UTC-4) the bucket open times in UTC are 13:30 and 14:30."""
    body = _load("timesales_15min.json")
    raw_bars = [
        TradierClient._normalize_timesales_bar(b) for b in TradierClient._extract_timesales(body)
    ]
    hourly = TradierClient._aggregate_to_hourly(raw_bars)

    assert len(hourly) == 2, f"expected exactly 2 buckets, got {len(hourly)}"

    # Bucket keys are open-aligned (:30:00Z), not UTC-hour aligned. The
    # previous UTC-bucket implementation would have emitted :00:00Z keys.
    assert hourly[0]["t"] == "2026-05-21T13:30:00Z"
    assert hourly[1]["t"] == "2026-05-21T14:30:00Z"

    # Bucket 1 (9:30-10:30 ET) = 9:30, 9:45, 10:00, 10:15 sub-bars.
    assert hourly[0]["o"] == pytest.approx(301.03)
    assert hourly[0]["h"] == pytest.approx(303.07)
    assert hourly[0]["l"] == pytest.approx(300.4)
    assert hourly[0]["c"] == pytest.approx(301.93)
    assert hourly[0]["v"] == 2239603 + 1152953 + 988800 + 1006204

    # Bucket 2 (10:30-11:30 ET) = 10:30, 10:45, 11:00, 11:15 sub-bars.
    assert hourly[1]["o"] == pytest.approx(301.93)
    assert hourly[1]["h"] == pytest.approx(303.36)
    assert hourly[1]["l"] == pytest.approx(301.5801)
    assert hourly[1]["c"] == pytest.approx(303.02)
    assert hourly[1]["v"] == 720557 + 556288 + 703173 + 1201398


# --- Fault payload handling --------------------------------------------------


def test_fault_payload_recognized():
    """A 200-OK body that contains "fault" should be treated as terminal
    error by the caller (the request layer is responsible for the actual
    None return; here we just confirm the shape detection)."""
    body = _load("fault_auth.json")
    assert "fault" in body
    assert body["fault"].get("faultstring") == "Invalid Access Token"
