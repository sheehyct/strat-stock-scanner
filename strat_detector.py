# strat_detector.py
"""
STRAT Pattern Detection Module
Identifies completed STRAT patterns from historical bar data
"""

from typing import List, Dict, Optional, Literal
from datetime import datetime

BarType = Literal["1", "2U", "2D", "3"]

class Bar:
    """Represents a single price bar with STRAT classification"""
    def __init__(self, timestamp: str, open_price: float, high: float, low: float, close: float, volume: int):
        self.timestamp = timestamp
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.bar_type: Optional[BarType] = None

    def classify_vs_previous(self, prev_bar: 'Bar') -> BarType:
        """Classify bar type relative to previous bar"""
        if not prev_bar:
            return "3"  # First bar defaults to 3

        # Type 1: Inside bar (high < prev high AND low > prev low)
        if self.high < prev_bar.high and self.low > prev_bar.low:
            return "1"

        # Type 2U: Outside bar up (high > prev high AND low <= prev low)
        elif self.high > prev_bar.high and self.low <= prev_bar.low:
            return "2U"

        # Type 2D: Outside bar down (high >= prev high AND low < prev low)
        elif self.high >= prev_bar.high and self.low < prev_bar.low:
            return "2D"

        # Type 3: Directional bar (doesn't contain or is contained by previous)
        else:
            return "3"

    def __repr__(self):
        return f"Bar({self.timestamp}, Type: {self.bar_type}, H:{self.high}, L:{self.low})"


class STRATPattern:
    """Detected STRAT pattern with metadata"""
    def __init__(self, pattern_type: str, bars: List[Bar], direction: str, confidence: str, description: str):
        self.pattern_type = pattern_type
        self.bars = bars
        self.direction = direction  # "bullish" or "bearish"
        self.confidence = confidence  # "high", "medium", "low"
        self.description = description
        self.entry_level = bars[-1].high if direction == "bullish" else bars[-1].low
        self.timestamp = bars[-1].timestamp

    def __repr__(self):
        return f"{self.pattern_type} ({self.direction}) - {self.confidence} confidence"


class STRATDetector:
    """Main STRAT pattern detection engine"""

    @staticmethod
    def classify_bars(bars: List[Dict]) -> List[Bar]:
        """Convert raw bar data to classified Bar objects"""
        bar_objects = []

        for bar_data in bars:
            bar = Bar(
                timestamp=bar_data['t'],
                open_price=bar_data['o'],
                high=bar_data['h'],
                low=bar_data['l'],
                close=bar_data['c'],
                volume=bar_data['v']
            )
            bar_objects.append(bar)

        # Classify each bar vs previous
        for i, bar in enumerate(bar_objects):
            if i == 0:
                bar.bar_type = "3"
            else:
                bar.bar_type = bar.classify_vs_previous(bar_objects[i-1])

        return bar_objects

    @staticmethod
    def detect_2_1_2_reversal(bars: List[Bar]) -> Optional[STRATPattern]:
        """
        Detect 2-1-2 reversal pattern (most reliable STRAT setup)
        Pattern: 2U/2D -> 1 -> 2U/2D (opposite direction)
        """
        if len(bars) < 3:
            return None

        # Check last 3 bars for 2-1-2
        for i in range(len(bars) - 2):
            bar1, bar2, bar3 = bars[i], bars[i+1], bars[i+2]

            # Bullish 2-1-2: 2D -> 1 -> 2U
            if bar1.bar_type == "2D" and bar2.bar_type == "1" and bar3.bar_type == "2U":
                return STRATPattern(
                    pattern_type="2-1-2 Reversal",
                    bars=[bar1, bar2, bar3],
                    direction="bullish",
                    confidence="high",
                    description=f"Bullish 2-1-2: Reversal from low ${bar1.low:.2f} through inside bar, breaking to ${bar3.high:.2f}"
                )

            # Bearish 2-1-2: 2U -> 1 -> 2D
            elif bar1.bar_type == "2U" and bar2.bar_type == "1" and bar3.bar_type == "2D":
                return STRATPattern(
                    pattern_type="2-1-2 Reversal",
                    bars=[bar1, bar2, bar3],
                    direction="bearish",
                    confidence="high",
                    description=f"Bearish 2-1-2: Reversal from high ${bar1.high:.2f} through inside bar, breaking to ${bar3.low:.2f}"
                )

        return None

    @staticmethod
    def detect_3_1_2_continuation(bars: List[Bar]) -> Optional[STRATPattern]:
        """
        Detect 3-1-2 continuation pattern
        Pattern: 3 (directional) -> 1 (inside) -> 2 (breakout in same direction)
        """
        if len(bars) < 3:
            return None

        for i in range(len(bars) - 2):
            bar1, bar2, bar3 = bars[i], bars[i+1], bars[i+2]

            if bar1.bar_type == "3" and bar2.bar_type == "1":
                # Bullish continuation: 3 up -> 1 -> 2U
                if bar1.close > bar1.open and bar3.bar_type == "2U":
                    return STRATPattern(
                        pattern_type="3-1-2 Continuation",
                        bars=[bar1, bar2, bar3],
                        direction="bullish",
                        confidence="high",
                        description=f"Bullish 3-1-2: Trend continuation breaking to new high ${bar3.high:.2f}"
                    )

                # Bearish continuation: 3 down -> 1 -> 2D
                elif bar1.close < bar1.open and bar3.bar_type == "2D":
                    return STRATPattern(
                        pattern_type="3-1-2 Continuation",
                        bars=[bar1, bar2, bar3],
                        direction="bearish",
                        confidence="high",
                        description=f"Bearish 3-1-2: Trend continuation breaking to new low ${bar3.low:.2f}"
                    )

        return None

    @staticmethod
    def detect_2_2_combo(bars: List[Bar]) -> Optional[STRATPattern]:
        """
        Detect 2-2 combo (volatile expansion pattern)
        Pattern: 2 -> 2 (consecutive outside bars)
        """
        if len(bars) < 2:
            return None

        for i in range(len(bars) - 1):
            bar1, bar2 = bars[i], bars[i+1]

            # Two consecutive 2U (bullish expansion)
            if bar1.bar_type == "2U" and bar2.bar_type == "2U":
                return STRATPattern(
                    pattern_type="2-2 Combo",
                    bars=[bar1, bar2],
                    direction="bullish",
                    confidence="medium",
                    description=f"Bullish 2-2: Volatile expansion to ${bar2.high:.2f} (watch for exhaustion)"
                )

            # Two consecutive 2D (bearish expansion)
            elif bar1.bar_type == "2D" and bar2.bar_type == "2D":
                return STRATPattern(
                    pattern_type="2-2 Combo",
                    bars=[bar1, bar2],
                    direction="bearish",
                    confidence="medium",
                    description=f"Bearish 2-2: Volatile expansion to ${bar2.low:.2f} (watch for exhaustion)"
                )

        return None

    @staticmethod
    def detect_inside_bar_setup(bars: List[Bar]) -> Optional[STRATPattern]:
        """
        Detect inside bar (Type 1) ready for breakout
        Recent inside bar with potential directional move
        """
        if len(bars) < 2:
            return None

        last_bar = bars[-1]
        prev_bar = bars[-2] if len(bars) >= 2 else None

        # Current bar is inside bar
        if last_bar.bar_type == "1":
            # Determine likely direction based on prior trend
            prior_trend = "bullish" if prev_bar and prev_bar.close > prev_bar.open else "bearish"

            return STRATPattern(
                pattern_type="Inside Bar Setup",
                bars=[prev_bar, last_bar] if prev_bar else [last_bar],
                direction=prior_trend,
                confidence="low",
                description=f"Inside bar at ${last_bar.close:.2f} - Watch for breakout (High: ${last_bar.high:.2f}, Low: ${last_bar.low:.2f})"
            )

        return None

    @staticmethod
    def scan_for_patterns(bars: List[Dict]) -> List[STRATPattern]:
        """
        Scan bar data for all STRAT patterns
        Returns list of detected patterns ordered by confidence
        """
        if len(bars) < 2:
            return []

        classified_bars = STRATDetector.classify_bars(bars)
        patterns = []

        # Detect patterns in order of priority
        pattern_2_1_2 = STRATDetector.detect_2_1_2_reversal(classified_bars)
        if pattern_2_1_2:
            patterns.append(pattern_2_1_2)

        pattern_3_1_2 = STRATDetector.detect_3_1_2_continuation(classified_bars)
        if pattern_3_1_2:
            patterns.append(pattern_3_1_2)

        pattern_2_2 = STRATDetector.detect_2_2_combo(classified_bars)
        if pattern_2_2:
            patterns.append(pattern_2_2)

        inside_bar = STRATDetector.detect_inside_bar_setup(classified_bars)
        if inside_bar:
            patterns.append(inside_bar)

        # Sort by confidence (high > medium > low)
        confidence_order = {"high": 3, "medium": 2, "low": 1}
        patterns.sort(key=lambda p: confidence_order[p.confidence], reverse=True)

        return patterns


def format_pattern_report(ticker: str, patterns: List[STRATPattern], current_price: float) -> str:
    """Format detected patterns into readable report"""
    if not patterns:
        return f"**{ticker}**: No STRAT patterns detected"

    report = f"**{ticker}** - ${current_price:.2f}\n"

    for pattern in patterns:
        direction_label = "[BULLISH]" if pattern.direction == "bullish" else "[BEARISH]"
        report += f"{direction_label} **{pattern.pattern_type}** ({pattern.confidence} confidence)\n"
        report += f"   {pattern.description}\n"
        report += f"   Entry: ${pattern.entry_level:.2f}\n"

    return report
