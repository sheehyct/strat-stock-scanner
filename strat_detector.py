# strat_detector.py
"""
STRAT Pattern Detection Module
Identifies completed STRAT patterns from historical bar data
Includes ATR/Volume metrics and TFC scoring
"""

from typing import List, Dict, Optional, Literal, Tuple
from datetime import datetime
from dataclasses import dataclass

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


@dataclass
class StockMetrics:
    """ATR, Volume, and other metrics for filtering"""
    ticker: str
    price: float
    atr_14: float
    atr_percent: float  # ATR as % of price
    avg_volume: float   # 20-day average volume
    dollar_volume: float  # avg_volume * price

    def passes_filter(
        self,
        min_atr: float = 0.0,
        min_atr_percent: float = 0.0,
        min_dollar_volume: float = 0.0
    ) -> bool:
        """Check if stock passes ATR/volume filters"""
        return (
            self.atr_14 >= min_atr and
            self.atr_percent >= min_atr_percent and
            self.dollar_volume >= min_dollar_volume
        )

    def __str__(self):
        return f"ATR: ${self.atr_14:.2f} ({self.atr_percent:.1f}%) | Vol: {self.avg_volume/1e6:.1f}M | $Vol: ${self.dollar_volume/1e6:.1f}M"


@dataclass
class TimeframeBias:
    """Bias information for a single timeframe"""
    timeframe: str
    bias: str  # "bullish", "bearish", "neutral"
    pattern: Optional[str]
    bar_type: str
    confidence: str


@dataclass
class TFCScore:
    """Timeframe Continuity score and details"""
    score: int  # 0-4 (number of aligned timeframes)
    quality: str  # A+, A, B, C, D
    aligned_timeframes: List[str]
    dominant_bias: str
    details: List[TimeframeBias]

    def __str__(self):
        return f"TFC {self.score}/4 ({self.quality}) - {self.dominant_bias.upper()} | Aligned: {', '.join(self.aligned_timeframes)}"


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
    def calculate_atr(bars: List[Dict], period: int = 14) -> float:
        """
        Calculate Average True Range

        Args:
            bars: List of OHLCV bar dictionaries
            period: ATR period (default 14)

        Returns:
            ATR value or 0 if insufficient data
        """
        if len(bars) < period + 1:
            # Not enough data, calculate with what we have
            if len(bars) < 2:
                return 0.0
            period = len(bars) - 1

        true_ranges = []

        for i in range(1, len(bars)):
            high = bars[i]['h']
            low = bars[i]['l']
            prev_close = bars[i-1]['c']

            # True Range = max of:
            # 1. Current high - current low
            # 2. |Current high - previous close|
            # 3. |Current low - previous close|
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        # Use simple moving average for ATR
        if len(true_ranges) >= period:
            atr = sum(true_ranges[-period:]) / period
        else:
            atr = sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

        return atr

    @staticmethod
    def calculate_avg_volume(bars: List[Dict], period: int = 20) -> float:
        """
        Calculate average volume

        Args:
            bars: List of OHLCV bar dictionaries
            period: Averaging period (default 20)

        Returns:
            Average volume
        """
        if not bars:
            return 0.0

        volumes = [bar['v'] for bar in bars]

        if len(volumes) >= period:
            return sum(volumes[-period:]) / period
        else:
            return sum(volumes) / len(volumes)

    @staticmethod
    def get_stock_metrics(ticker: str, bars: List[Dict]) -> StockMetrics:
        """
        Calculate all metrics for a stock

        Args:
            ticker: Stock symbol
            bars: Historical bar data

        Returns:
            StockMetrics object with ATR, volume, etc.
        """
        if not bars:
            return StockMetrics(
                ticker=ticker,
                price=0.0,
                atr_14=0.0,
                atr_percent=0.0,
                avg_volume=0.0,
                dollar_volume=0.0
            )

        price = bars[-1]['c']
        atr = STRATDetector.calculate_atr(bars, period=14)
        avg_vol = STRATDetector.calculate_avg_volume(bars, period=20)

        return StockMetrics(
            ticker=ticker,
            price=price,
            atr_14=atr,
            atr_percent=(atr / price * 100) if price > 0 else 0.0,
            avg_volume=avg_vol,
            dollar_volume=avg_vol * price
        )

    @staticmethod
    def get_timeframe_bias(bars: List[Dict]) -> Tuple[str, Optional[str], str]:
        """
        Determine bias for a timeframe based on recent bar action

        Returns:
            Tuple of (bias, pattern_type, last_bar_type)
        """
        if not bars or len(bars) < 2:
            return ("neutral", None, "?")

        classified = STRATDetector.classify_bars(bars)
        patterns = STRATDetector.scan_for_patterns(bars)

        last_bar = classified[-1]
        last_bar_type = last_bar.bar_type

        # Determine bias from patterns first
        if patterns:
            # Get highest confidence bullish/bearish pattern
            bullish_patterns = [p for p in patterns if p.direction == "bullish"]
            bearish_patterns = [p for p in patterns if p.direction == "bearish"]

            if bullish_patterns and (not bearish_patterns or
                bullish_patterns[0].confidence >= bearish_patterns[0].confidence):
                return ("bullish", bullish_patterns[0].pattern_type, last_bar_type)
            elif bearish_patterns:
                return ("bearish", bearish_patterns[0].pattern_type, last_bar_type)

        # Fall back to last bar type
        if last_bar_type == "2U":
            return ("bullish", None, last_bar_type)
        elif last_bar_type == "2D":
            return ("bearish", None, last_bar_type)
        elif last_bar_type == "3":
            # Check close vs open for directional 3
            if last_bar.close > last_bar.open:
                return ("bullish", None, last_bar_type)
            elif last_bar.close < last_bar.open:
                return ("bearish", None, last_bar_type)

        return ("neutral", None, last_bar_type)

    @staticmethod
    def calculate_tfc_score(timeframe_data: Dict[str, List[Dict]]) -> TFCScore:
        """
        Calculate Timeframe Continuity score

        Args:
            timeframe_data: Dict mapping timeframe name to bar data
                           e.g., {"weekly": [...], "daily": [...], "60min": [...], "15min": [...]}

        Returns:
            TFCScore object with alignment details
        """
        details = []
        biases = {"bullish": 0, "bearish": 0, "neutral": 0}

        timeframe_order = ["weekly", "daily", "60min", "15min"]

        for tf in timeframe_order:
            bars = timeframe_data.get(tf, [])
            if not bars:
                details.append(TimeframeBias(
                    timeframe=tf,
                    bias="neutral",
                    pattern=None,
                    bar_type="?",
                    confidence="none"
                ))
                biases["neutral"] += 1
                continue

            bias, pattern, bar_type = STRATDetector.get_timeframe_bias(bars)

            # Get confidence from pattern if available
            patterns = STRATDetector.scan_for_patterns(bars)
            confidence = "none"
            if patterns:
                matching = [p for p in patterns if p.direction == bias]
                if matching:
                    confidence = matching[0].confidence

            details.append(TimeframeBias(
                timeframe=tf,
                bias=bias,
                pattern=pattern,
                bar_type=bar_type,
                confidence=confidence
            ))
            biases[bias] += 1

        # Determine dominant bias
        if biases["bullish"] > biases["bearish"]:
            dominant = "bullish"
            aligned = [d.timeframe for d in details if d.bias == "bullish"]
        elif biases["bearish"] > biases["bullish"]:
            dominant = "bearish"
            aligned = [d.timeframe for d in details if d.bias == "bearish"]
        else:
            dominant = "neutral"
            aligned = []

        # Calculate score (0-4)
        score = max(biases["bullish"], biases["bearish"])

        # Determine quality grade
        if score >= 4:
            quality = "A+"
        elif score == 3:
            quality = "A"
        elif score == 2:
            quality = "B"
        elif score == 1:
            quality = "C"
        else:
            quality = "D"

        return TFCScore(
            score=score,
            quality=quality,
            aligned_timeframes=aligned,
            dominant_bias=dominant,
            details=details
        )

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


def format_pattern_report(ticker: str, patterns: List[STRATPattern], current_price: float, metrics: Optional[StockMetrics] = None) -> str:
    """Format detected patterns into readable report"""
    if not patterns:
        return f"**{ticker}**: No STRAT patterns detected"

    report = f"**{ticker}** - ${current_price:.2f}\n"

    # Add metrics if available
    if metrics:
        report += f"Metrics: {metrics}\n"

    for pattern in patterns:
        direction_label = "[BULLISH]" if pattern.direction == "bullish" else "[BEARISH]"
        report += f"{direction_label} **{pattern.pattern_type}** ({pattern.confidence} confidence)\n"
        report += f"   {pattern.description}\n"
        report += f"   Entry: ${pattern.entry_level:.2f}\n"

    return report


def format_tfc_report(ticker: str, tfc: TFCScore, metrics: Optional[StockMetrics] = None) -> str:
    """Format TFC analysis into readable report"""
    report = f"**{ticker}** - {tfc}\n"

    if metrics:
        report += f"Metrics: {metrics}\n"

    report += "\n**Timeframe Breakdown:**\n"
    for detail in tfc.details:
        bias_indicator = "[BULL]" if detail.bias == "bullish" else "[BEAR]" if detail.bias == "bearish" else "[NEUT]"
        pattern_str = f" ({detail.pattern})" if detail.pattern else ""
        report += f"  {bias_indicator} {detail.timeframe.upper()}: {detail.bias}{pattern_str} - Type {detail.bar_type}\n"

    return report
