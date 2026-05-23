"""
Tests for STRATPattern.entry_level (the "Key Level" surfaced in scanner output).

Per strat-methodology references/ENTRY_MECHANICS.md, the entry trigger price
depends on the pattern shape, not just direction:

- X-1-2 confirmed (2-1-2 Reversal, 3-1-2 Continuation): inside bar (bars[1])
  high/low, offset by +/- 0.01.
- X-1 setups (2-1 Setup, 3-1 Setup, Inside Bar Setup): inside bar (last bar)
  high/low, offset by +/- 0.01.
- 2-2 patterns (Reversal, Continuation): reference bar (bars[0]) high/low,
  offset by +/- 0.01.

Earlier code used bars[-1].high/low for every pattern, which produced
trigger prices ABOVE the actual trigger (sometimes by several dollars) and
could mislead users into placing orders too late.
"""

from strat_detector import STRATDetector

# Reuse the small bar-construction helper pattern from test_strat_correctness
def _bar(t: str, high: float, low: float, close: float | None = None) -> dict:
    return {
        "t": t,
        "o": close if close is not None else (high + low) / 2,
        "h": high,
        "l": low,
        "c": close if close is not None else (high + low) / 2,
        "v": 1_000_000,
    }


def _find(patterns, pattern_type):
    matches = [p for p in patterns if p.pattern_type == pattern_type]
    assert matches, f"Expected {pattern_type} in {[p.pattern_type for p in patterns]}"
    return matches[0]


# --- 2-1-2 Reversal --------------------------------------------------------


def test_2_1_2_bullish_entry_uses_inside_bar_high_plus_offset():
    """Bullish 2-1-2: trigger = bars[1].high + 0.01 (inside bar high)."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=110, low=100),
        _bar("2024-01-02T00:00:00Z", high=105, low=95),    # 2D
        _bar("2024-01-03T00:00:00Z", high=104, low=96),    # 1 inside - trigger here
        _bar("2024-01-04T00:00:00Z", high=107, low=97),    # 2U breakout
    ]
    pattern = _find(STRATDetector.scan_for_patterns(bars), "2-1-2 Reversal")
    assert pattern.direction == "bullish"
    # Inside bar high = 104, trigger = 104 + 0.01
    assert abs(pattern.entry_level - 104.01) < 1e-9, (
        f"Expected 104.01, got {pattern.entry_level}"
    )
    # Critical: should NOT be the breakout bar high (107.00)
    assert pattern.entry_level < 107.00


def test_2_1_2_bearish_entry_uses_inside_bar_low_minus_offset():
    """Bearish 2-1-2: trigger = bars[1].low - 0.01 (inside bar low)."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=110, low=100),
        _bar("2024-01-02T00:00:00Z", high=115, low=105),   # 2U
        _bar("2024-01-03T00:00:00Z", high=114, low=106),   # 1 inside - trigger here
        _bar("2024-01-04T00:00:00Z", high=113, low=104),   # 2D breakout
    ]
    pattern = _find(STRATDetector.scan_for_patterns(bars), "2-1-2 Reversal")
    assert pattern.direction == "bearish"
    # Inside bar low = 106, trigger = 106 - 0.01
    assert abs(pattern.entry_level - 105.99) < 1e-9, (
        f"Expected 105.99, got {pattern.entry_level}"
    )
    # Critical: should NOT be the breakout bar low (104.00)
    assert pattern.entry_level > 104.00


# --- 3-1-2 Continuation ----------------------------------------------------


def test_3_1_2_bullish_entry_uses_inside_bar_high():
    """Bullish 3-1-2: trigger = bars[1].high + 0.01 (inside bar high).

    The Type 3 bar must be GREEN (close > open) for the bullish branch of
    detect_3_1_2_continuation to fire. The _bar helper collapses open to
    close when close is supplied, so this fixture passes the Type 3 dict
    inline with explicit open < close.
    """
    bars = [
        _bar("2024-01-01T00:00:00Z", high=100, low=95),
        {"t": "2024-01-02T00:00:00Z", "o": 95.0, "h": 105.0, "l": 94.0, "c": 104.0, "v": 1_000_000},
        _bar("2024-01-03T00:00:00Z", high=104, low=96),    # 1 inside - trigger
        _bar("2024-01-04T00:00:00Z", high=107, low=97),    # 2U breakout
    ]
    pattern = _find(STRATDetector.scan_for_patterns(bars), "3-1-2 Continuation")
    assert pattern.direction == "bullish"
    assert abs(pattern.entry_level - 104.01) < 1e-9
    assert pattern.entry_level < 107.00  # not the breakout bar high


# --- 2-2 Reversal ----------------------------------------------------------


def test_2_2_reversal_bullish_entry_uses_reference_bar_high():
    """Bullish 2-2 Reversal: trigger = bars[0].high + 0.01 (reference bar)."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=100, low=95),    # reference (2D)
        _bar("2024-01-02T00:00:00Z", high=99, low=94),     # 2D
        _bar("2024-01-03T00:00:00Z", high=101, low=95),    # 2U - reversal bar
    ]
    pattern = _find(STRATDetector.scan_for_patterns(bars), "2-2 Reversal")
    assert pattern.direction == "bullish"
    # Reference bar (bars[0] of the pattern's bars list) = the 2D bar with high=99
    # NB: the pattern's bars list is [2D-bar, 2U-bar]; reference is the 2D.
    # Trigger = 99 + 0.01 = 99.01
    assert abs(pattern.entry_level - 99.01) < 1e-9, (
        f"Expected 99.01, got {pattern.entry_level}"
    )
    # Critical: should NOT be the reversal bar high (101.00)
    assert pattern.entry_level < 101.00


def test_2_2_reversal_bearish_entry_uses_reference_bar_low():
    """Bearish 2-2 Reversal: trigger = bars[0].low - 0.01 (reference bar)."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=95, low=90),     # reference
        _bar("2024-01-02T00:00:00Z", high=100, low=92),    # 2U (reference for the 2-2 pattern)
        _bar("2024-01-03T00:00:00Z", high=99, low=91),     # 2D - reversal bar
    ]
    pattern = _find(STRATDetector.scan_for_patterns(bars), "2-2 Reversal")
    assert pattern.direction == "bearish"
    # Pattern's bars list = [2U, 2D]. Reference is the 2U with low=92.
    # Trigger = 92 - 0.01 = 91.99
    assert abs(pattern.entry_level - 91.99) < 1e-9, (
        f"Expected 91.99, got {pattern.entry_level}"
    )
    # Critical: should NOT be the reversal bar low (91.00)
    assert pattern.entry_level > 91.00


# --- Setups (X-1) ----------------------------------------------------------


def test_2_1_setup_bullish_entry_uses_inside_bar_high():
    """Bullish 2-1 Setup: trigger = inside bar high + 0.01 (awaiting breakout)."""
    bars = [
        _bar("2024-01-01T00:00:00Z", high=100, low=95),
        _bar("2024-01-02T00:00:00Z", high=99, low=94),     # 2D (the X)
        _bar("2024-01-03T00:00:00Z", high=98, low=95),     # 1 inside (awaiting breakout)
    ]
    pattern = _find(STRATDetector.scan_for_patterns(bars), "2-1 Setup")
    assert pattern.direction == "bullish"
    # Inside bar high = 98, trigger = 98 + 0.01
    assert abs(pattern.entry_level - 98.01) < 1e-9, (
        f"Expected 98.01, got {pattern.entry_level}"
    )


def test_inside_bar_setup_entry_uses_inside_bar_high():
    """Generic inside-bar setup falls back to the same inside-bar trigger.
    Built from a Type 1 last bar with no specific 2-1 or 3-1 setup match."""
    # Need a 2-bar fixture where:
    # bars[0] sets prior range; bars[1] is the inside bar
    # AND there's no preceding directional or Type 3 bar (because that
    # would be a 2-1 or 3-1 setup instead).
    # The detector defaults bars[0] to Type 3, so a 2-bar fixture
    # would qualify as a 3-1 setup. We need a 3-bar fixture where the
    # second bar is Type 1 (not directional, not 3), so the last bar
    # is also inside but inside-vs-inside isn't a setup type.
    # Easier: scan with a fixture that yields ONLY an inside-bar setup.
    # 3 bars: bar 0 = Type 3 default, bar 1 = 1 (vs bar 0), bar 2 = 1 (vs bar 1)
    bars = [
        _bar("2024-01-01T00:00:00Z", high=100, low=95),
        _bar("2024-01-02T00:00:00Z", high=99, low=96),     # 1 (inside vs bar 0)
        _bar("2024-01-03T00:00:00Z", high=99, low=96),     # 1 (inside vs bar 1)
    ]
    patterns = STRATDetector.scan_for_patterns(bars)
    pattern = _find(patterns, "Inside Bar Setup")
    # bars[-1].high = 99, trigger direction depends on prior trend.
    # bar[-2] (the prior bar in the setup) opened at (99+96)/2 = 97.5 and
    # closed the same (we don't supply a separate close), so prior_trend
    # is bearish by tie-breaking rule (close not > open). Trigger uses
    # inside bar low - 0.01.
    if pattern.direction == "bullish":
        assert abs(pattern.entry_level - 99.01) < 1e-9
    else:
        assert abs(pattern.entry_level - 95.99) < 1e-9


# --- Direct STRATPattern construction (no detector path) -------------------


def test_unknown_pattern_type_falls_back_with_offset():
    """An unrecognized pattern type uses bars[-1] high/low + offset rather
    than raising. Future-proofs against new pattern types not yet mapped."""
    from strat_detector import Bar, STRATPattern

    bar_a = Bar("2024-01-01T00:00:00Z", 100, 105, 95, 100, 1000000)
    bar_a.bar_type = "3"
    bar_b = Bar("2024-01-02T00:00:00Z", 100, 110, 100, 108, 1000000)
    bar_b.bar_type = "2U"

    pattern = STRATPattern(
        pattern_type="Made-Up Pattern",
        bars=[bar_a, bar_b],
        direction="bullish",
        confidence="low",
        description="test",
    )
    # Falls back to bars[-1].high + 0.01 = 110.01
    assert abs(pattern.entry_level - 110.01) < 1e-9
