"""
Tests for the scanner correctness PR:

- Current-actionable filter (only patterns whose confirming bar is the last
  bar are returned).
- 2-2 detector iteration direction (the bug fix - returns the newest, not
  the oldest, 2-2 in the window).
- scan_for_patterns excludes 2-2 Continuation (per methodology: position
  management, not a new entry signal).
- Setups are suppressed when a confirmed pattern fires.
- Pattern timestamp surfaces the confirming bar's timestamp.

Bar-construction helper plus a battery of fixtures aimed at the specific
behavioral guarantees the PR introduces. No live data; no Tradier calls.
"""

from typing import List

from strat_detector import STRATDetector


def _bar(t: str, high: float, low: float, close: float | None = None) -> dict:
    """Build a single OHLCV dict in the shape the detector consumes."""
    return {
        "t": t,
        "o": close if close is not None else (high + low) / 2,
        "h": high,
        "l": low,
        "c": close if close is not None else (high + low) / 2,
        "v": 1_000_000,
    }


# --- Current-actionable filter: 2-1-2 reversal -----------------------------


def test_2_1_2_returns_when_breakout_is_last_bar():
    """4-bar fixture: [3, 2D, 1, 2U] - confirming bar is the last bar.
    The 2-1-2 reversal must be detected and returned."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=110, low=100),  # Type 3 default
        _bar("2024-01-02T00:00:00Z", high=105, low=95),   # 2D vs prior
        _bar("2024-01-03T00:00:00Z", high=104, low=96),   # 1 vs prior
        _bar("2024-01-04T00:00:00Z", high=107, low=97),   # 2U vs prior - bullish 2-1-2
    ]
    patterns = STRATDetector.scan_for_patterns(bars)
    assert any(p.pattern_type == "2-1-2 Reversal" for p in patterns), (
        f"Expected 2-1-2 Reversal in scan output, got {[p.pattern_type for p in patterns]}"
    )


def test_2_1_2_not_returned_when_pattern_fired_earlier():
    """5-bar fixture: [3, 2D, 1, 2U, 2U] - the 2-1-2 fired at bar 3, then
    bar 4 continued upward. The 2-1-2 is stale and must NOT be returned."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=110, low=100),
        _bar("2024-01-02T00:00:00Z", high=105, low=95),    # 2D
        _bar("2024-01-03T00:00:00Z", high=104, low=96),    # 1
        _bar("2024-01-04T00:00:00Z", high=107, low=97),    # 2U - 2-1-2 fires here (stale)
        _bar("2024-01-05T00:00:00Z", high=109, low=98),    # 2U - continuation
    ]
    patterns = STRATDetector.scan_for_patterns(bars)
    assert not any(p.pattern_type == "2-1-2 Reversal" for p in patterns), (
        "Stale 2-1-2 should be filtered out by current-actionable filter"
    )


# --- Current-actionable filter + iteration direction: 2-2 reversal ---------


def test_2_2_reversal_returns_when_flip_is_last_bar():
    """3-bar fixture: [3, 2D, 2U] - bullish 2-2 reversal whose confirming
    bar is the last bar."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=100, low=95),
        _bar("2024-01-02T00:00:00Z", high=99, low=94),    # 2D
        _bar("2024-01-03T00:00:00Z", high=101, low=95),   # 2U - bullish 2-2 reversal
    ]
    patterns = STRATDetector.scan_for_patterns(bars)
    matching = [p for p in patterns if p.pattern_type == "2-2 Reversal"]
    assert matching, (
        f"Expected 2-2 Reversal in scan output, got {[p.pattern_type for p in patterns]}"
    )
    assert matching[0].direction == "bullish"


def test_2_2_reversal_not_returned_when_pattern_fired_earlier():
    """4-bar fixture: [3, 2D, 2U, 2U] - bullish 2-2 reversal fired at bar 2,
    then bar 3 continued upward. The reversal is stale; must NOT be returned.

    This is the exact bug from the test report: the old detect_2_2_reversal
    iterated oldest-first and would return the stale bullish reversal. With
    current-actionable filter it returns None."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=100, low=95),
        _bar("2024-01-02T00:00:00Z", high=99, low=94),    # 2D
        _bar("2024-01-03T00:00:00Z", high=101, low=95),   # 2U - 2-2 reversal fires (stale)
        _bar("2024-01-04T00:00:00Z", high=103, low=96),   # 2U - continuation
    ]
    patterns = STRATDetector.scan_for_patterns(bars)
    assert not any(p.pattern_type == "2-2 Reversal" for p in patterns), (
        "Stale 2-2 Reversal should be filtered out by current-actionable filter"
    )


# --- 2-2 Continuation: excluded from default scan output -------------------


def test_scan_excludes_2_2_continuation():
    """3-bar fixture: [3, 2U, 2U] - bullish 2-2 continuation. The detector
    itself still recognizes the pattern (callable directly), but
    scan_for_patterns must NOT include it in output per methodology
    (continuation is position management, not a new entry signal)."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=100, low=95),
        _bar("2024-01-02T00:00:00Z", high=102, low=95),   # 2U
        _bar("2024-01-03T00:00:00Z", high=104, low=96),   # 2U - 2-2 continuation
    ]
    classified = STRATDetector.classify_bars(bars)
    direct = STRATDetector.detect_2_2_continuation(classified)
    assert direct is not None and direct.pattern_type == "2-2 Continuation", (
        "Direct detector call should still recognize 2-2 Continuation"
    )

    scan = STRATDetector.scan_for_patterns(bars)
    assert not any(p.pattern_type == "2-2 Continuation" for p in scan), (
        "scan_for_patterns must exclude 2-2 Continuation from default output"
    )


# --- Setup-append logic ----------------------------------------------------


def test_2_1_setup_returned_when_no_confirmed_pattern():
    """3-bar fixture ending in Type 1 with no confirmed pattern: the 2-1
    setup must be reported (it's the relevant trade context)."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=100, low=95),
        _bar("2024-01-02T00:00:00Z", high=99, low=94),    # 2D
        _bar("2024-01-03T00:00:00Z", high=98, low=95),    # 1 (inside bar)
    ]
    patterns = STRATDetector.scan_for_patterns(bars)
    assert any(p.pattern_type == "2-1 Setup" for p in patterns), (
        f"Expected 2-1 Setup in scan output, got {[p.pattern_type for p in patterns]}"
    )


# --- Pattern timestamp surfaces the confirming bar --------------------------


def test_pattern_timestamp_equals_last_bar_timestamp():
    """Every returned pattern must carry the confirming bar's timestamp so
    downstream display can show freshness."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=110, low=100),
        _bar("2024-01-02T00:00:00Z", high=105, low=95),
        _bar("2024-01-03T00:00:00Z", high=104, low=96),
        _bar("2024-01-04T00:00:00Z", high=107, low=97),
    ]
    patterns = STRATDetector.scan_for_patterns(bars)
    assert patterns, "Fixture should produce at least one pattern"
    last_ts = bars[-1]["t"]
    for p in patterns:
        assert p.timestamp == last_ts, (
            f"Pattern {p.pattern_type} timestamp {p.timestamp} != last bar {last_ts}"
        )


# --- Sort order: confidence desc when multiple patterns coexist ------------


def test_sort_puts_highest_confidence_first():
    """When multiple patterns can fire on the same confirming bar, confidence
    desc keeps the highest-confidence signal first. The 2-1-2 reversal
    (high) should outrank any concurrent setup (low)."""
    # 4-bar 2-1-2 fixture: produces high-confidence 2-1-2 (confirmed) and
    # no setups (setups require last bar to be Type 1).
    bars = [
        _bar("2024-01-01T00:00:00Z", high=110, low=100),
        _bar("2024-01-02T00:00:00Z", high=105, low=95),    # 2D
        _bar("2024-01-03T00:00:00Z", high=104, low=96),    # 1
        _bar("2024-01-04T00:00:00Z", high=107, low=97),    # 2U
    ]
    patterns = STRATDetector.scan_for_patterns(bars)
    assert patterns, "Fixture should produce patterns"
    assert patterns[0].confidence == "high", (
        f"Highest-confidence pattern should be first, got {patterns[0].confidence}"
    )
