# strat_detector.py
"""
STRAT Pattern Detection Module
Identifies completed STRAT patterns from historical bar data
Includes ATR/Volume metrics and TFC scoring
"""

from typing import List, Dict, Optional, Literal
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
import pytz

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
        self.is_forming: bool = False  # True if bar is still forming (intraday)

    def classify_vs_previous(self, prev_bar: 'Bar') -> BarType:
        """Classify bar type relative to previous bar"""
        if not prev_bar:
            return "3"  # First bar defaults to 3

        broke_high = self.high > prev_bar.high
        broke_low = self.low < prev_bar.low

        # Type 3: Outside bar (breaks both high AND low)
        if broke_high and broke_low:
            return "3"

        # Type 2U: Directional up (breaks high only)
        elif broke_high and not broke_low:
            return "2U"

        # Type 2D: Directional down (breaks low only)
        elif not broke_high and broke_low:
            return "2D"

        # Type 1: Inside bar (breaks neither)
        else:
            return "1"

    def __repr__(self):
        forming_str = " (forming)" if self.is_forming else ""
        return f"Bar({self.timestamp}, Type: {self.bar_type}{forming_str}, H:{self.high}, L:{self.low})"


class STRATPattern:
    """Detected STRAT pattern with metadata"""
    def __init__(self, pattern_type: str, bars: List[Bar], direction: str, confidence: str, description: str):
        self.pattern_type = pattern_type
        self.bars = bars
        self.direction = direction  # "bullish" or "bearish"
        self.confidence = confidence  # "high", "medium", "low"
        self.description = description
        self.timestamp = bars[-1].timestamp
        self.entry_level = self._compute_entry_level()

    def _compute_entry_level(self) -> float:
        """Compute the methodology-correct entry trigger price.

        Per strat-methodology references/ENTRY_MECHANICS.md, the trigger price
        depends on the pattern shape, not just on whether the signal is
        bullish or bearish:

        - X-1-2 confirmed patterns (2-1-2 Reversal, 3-1-2 Continuation):
          trigger lives on the inside bar (bars[1]). Bullish: inside high
          + 0.01. Bearish: inside low - 0.01.
        - X-1 setups (2-1 Setup, 3-1 Setup, Inside Bar Setup): trigger
          lives on the inside bar (bars[-1], which equals bars[1] for the
          2-bar setup shape). Same +/- 0.01 offset.
        - 2-2 patterns (Reversal, Continuation): trigger lives on the
          reference bar (bars[0]). Bullish: reference high + 0.01.
          Bearish: reference low - 0.01.

        The +/- 0.01 cent offset matches the methodology's "enter on the
        break" rule (price must STRICTLY cross the bar level to fire).
        """
        bullish = self.direction == "bullish"
        offset = 0.01 if bullish else -0.01

        x_1_2_patterns = ("2-1-2 Reversal", "3-1-2 Continuation")
        x_1_setups = ("2-1 Setup", "3-1 Setup", "Inside Bar Setup")
        two_two_patterns = ("2-2 Reversal", "2-2 Continuation")

        if self.pattern_type in x_1_2_patterns:
            inside = self.bars[1]
            level = inside.high if bullish else inside.low
        elif self.pattern_type in x_1_setups:
            inside = self.bars[-1]
            level = inside.high if bullish else inside.low
        elif self.pattern_type in two_two_patterns:
            ref = self.bars[0]
            level = ref.high if bullish else ref.low
        else:
            # Unrecognized pattern type - fall back to last bar high/low
            # with offset. Surfaces a usable number even for future pattern
            # types that haven't been mapped yet.
            level = self.bars[-1].high if bullish else self.bars[-1].low

        return level + offset

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
    is_forming: bool = False  # True if bar is still forming


@dataclass
class TFCScore:
    """Timeframe Continuity score and details"""
    score: int  # 0-5 (number of aligned timeframes)
    quality: str  # A+, A, B, C, D
    aligned_timeframes: List[str]
    dominant_bias: str
    details: List[TimeframeBias]
    bullish_count: int = 0  # Number of bullish timeframes
    bearish_count: int = 0  # Number of bearish timeframes
    neutral_count: int = 0  # Number of neutral timeframes (Type 1 / no data)

    def __str__(self):
        bias_breakdown = f"{self.bullish_count} Bull / {self.bearish_count} Bear / {self.neutral_count} Neutral"
        return f"TFC {self.score}/5 ({self.quality}) - {self.dominant_bias.upper()} | {bias_breakdown}"


class STRATDetector:
    """Main STRAT pattern detection engine"""

    # Timeframe to minutes mapping for forming bar detection
    TIMEFRAME_MINUTES = {
        "1Min": 1,
        "5Min": 5,
        "15Min": 15,
        "30Min": 30,
        "1Hour": 60,
        "1Day": 1440,  # Daily bars - typically don't need forming check
        "1Week": 10080,
        "1Month": 43200,
    }

    @staticmethod
    def is_bar_forming(bar_timestamp: str, timeframe: str = "1Day") -> bool:
        """
        Determine if a bar is still forming based on timestamp and timeframe.

        For intraday timeframes (15min, 60min), checks if the bar's timestamp
        falls within the current time period.

        Args:
            bar_timestamp: ISO format timestamp from bar data
            timeframe: Alpaca timeframe string (e.g., '1Hour', '15Min', '1Day')

        Returns:
            True if the bar is still forming, False if closed
        """
        try:
            # Parse bar timestamp
            if 'T' in bar_timestamp:
                # ISO format with time
                bar_dt = datetime.fromisoformat(bar_timestamp.replace('Z', '+00:00'))
            else:
                # Date only - assume market close (daily bars)
                bar_dt = datetime.strptime(bar_timestamp, '%Y-%m-%d')
                bar_dt = bar_dt.replace(tzinfo=timezone.utc)

            # Get current time in US Eastern
            eastern = pytz.timezone('America/New_York')
            now = datetime.now(eastern)

            # For daily and higher timeframes, bars are always closed at end of day
            if timeframe in ["1Day", "1Week", "1Month"]:
                # Daily bars: check if bar is from today and market is still open
                bar_date = bar_dt.astimezone(eastern).date()
                today = now.date()
                if bar_date == today:
                    # Market hours: 9:30 AM - 4:00 PM ET
                    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
                    if now < market_close:
                        return True
                return False

            # For intraday timeframes
            minutes = STRATDetector.TIMEFRAME_MINUTES.get(timeframe, 60)
            bar_dt_eastern = bar_dt.astimezone(eastern)

            # Calculate bar end time
            bar_end = bar_dt_eastern + timedelta(minutes=minutes)

            # Bar is forming if current time is before bar end
            return now < bar_end

        except Exception as e:
            # On error, assume bar is closed (conservative)
            return False

    @staticmethod
    def classify_bars(bars: List[Dict], timeframe: str = "1Day") -> List[Bar]:
        """
        Convert raw bar data to classified Bar objects.

        Args:
            bars: List of OHLCV bar dictionaries
            timeframe: Alpaca timeframe string for forming bar detection

        Returns:
            List of classified Bar objects
        """
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

        # Mark last bar as forming if applicable (for intraday timeframes)
        if bar_objects and timeframe in ["1Hour", "15Min", "30Min", "5Min", "1Min"]:
            last_bar = bar_objects[-1]
            last_bar.is_forming = STRATDetector.is_bar_forming(last_bar.timestamp, timeframe)

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
    def classify_bar_direction(bar: Bar) -> str:
        """
        Classify bar direction for TFC scoring using bar type only.

        Per STRAT methodology, TFC measures the directional state of each
        timeframe independently using only bar classification:
        - Type 1 (inside): Always "neutral" - indecision, excluded from TFC
        - Type 2U: "bullish" - directional up
        - Type 2D: "bearish" - directional down
        - Type 3 (outside): Direction by candle color (Close > Open = bullish)

        This separates TFC scoring from pattern detection for cleaner analysis.

        Args:
            bar: Classified Bar object

        Returns:
            "bullish", "bearish", or "neutral"
        """
        if bar.bar_type == "2U":
            return "bullish"
        elif bar.bar_type == "2D":
            return "bearish"
        elif bar.bar_type == "3":
            # Type 3: direction by candle color
            if bar.close > bar.open:
                return "bullish"
            elif bar.close < bar.open:
                return "bearish"
            return "neutral"  # Doji-like Type 3
        # Type 1 and anything else
        return "neutral"

    @staticmethod
    def calculate_tfc_score(timeframe_data: Dict[str, List[Dict]]) -> TFCScore:
        """
        Calculate Timeframe Continuity score using bar-type-only bias.

        Uses classify_bar_direction() for pure directional state assessment,
        separate from pattern detection. This matches STRAT methodology where
        TFC measures the raw directional state of each timeframe.

        Args:
            timeframe_data: Dict mapping timeframe name to bar data
                           e.g., {"weekly": [...], "daily": [...], "60min": [...], "15min": [...]}

        Returns:
            TFCScore object with alignment details
        """
        details = []
        biases = {"bullish": 0, "bearish": 0, "neutral": 0}

        timeframe_mapping = {
            "monthly": "1Month",
            "weekly": "1Week",
            "daily": "1Day",
            "60min": "1Hour",
            "15min": "15Min"
        }

        timeframe_order = ["monthly", "weekly", "daily", "60min", "15min"]

        for tf in timeframe_order:
            bars = timeframe_data.get(tf, [])
            alpaca_tf = timeframe_mapping.get(tf, "1Day")

            if not bars or len(bars) < 2:
                details.append(TimeframeBias(
                    timeframe=tf,
                    bias="neutral",
                    pattern=None,
                    bar_type="?",
                    confidence="none",
                    is_forming=False
                ))
                biases["neutral"] += 1
                continue

            # Classify bars and get last bar's direction
            classified = STRATDetector.classify_bars(bars, alpaca_tf)
            last_bar = classified[-1]
            direction = STRATDetector.classify_bar_direction(last_bar)

            # Get pattern info separately (for display, not for TFC scoring)
            patterns = STRATDetector.scan_for_patterns(bars, alpaca_tf)
            pattern_name = None
            confidence = "none"
            if patterns:
                # Find pattern matching the bar's direction
                matching = [p for p in patterns if p.direction == direction]
                top = matching[0] if matching else patterns[0]
                pattern_name = top.pattern_type
                confidence = top.confidence

            details.append(TimeframeBias(
                timeframe=tf,
                bias=direction,
                pattern=pattern_name,
                bar_type=last_bar.bar_type,
                confidence=confidence,
                is_forming=last_bar.is_forming
            ))

            biases[direction] += 1

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

        score = max(biases["bullish"], biases["bearish"])

        if score >= 5:
            quality = "A+"
        elif score >= 4:
            quality = "A"
        elif score == 3:
            quality = "B"
        elif score == 2:
            quality = "C"
        else:
            quality = "D"

        return TFCScore(
            score=score,
            quality=quality,
            aligned_timeframes=aligned,
            dominant_bias=dominant,
            details=details,
            bullish_count=biases["bullish"],
            bearish_count=biases["bearish"],
            neutral_count=biases["neutral"]
        )

    @staticmethod
    def get_contextual_tfc(tfc: 'TFCScore', detection_timeframe: str) -> Dict[str, any]:
        """
        Get timeframe-appropriate TFC assessment for a given detection timeframe.

        Key insight from workspace research (EQUITY-44, 55, 63, 89):
        Checking lower timeframes for higher timeframe patterns causes false filtering.
        A daily pattern doesn't need 15-minute alignment to be valid.

        Args:
            tfc: Full TFC score from calculate_tfc_score()
            detection_timeframe: Where the pattern was detected
                "15Min", "1Hour", "1Day", "1Week", "1Month"

        Returns:
            Dict with contextual scoring:
            {
                'effective_score': int,
                'max_possible': int,
                'effective_quality': str,
                'relevant_timeframes': list,
                'aligned_in_context': list,
                'passes': bool
            }
        """
        # Timeframe-appropriate requirements (ported from workspace)
        requirements = {
            "15Min": {"timeframes": ["monthly", "weekly", "daily", "60min", "15min"], "min": 3},
            "1Hour": {"timeframes": ["monthly", "weekly", "daily", "60min"], "min": 3},
            "1Day":  {"timeframes": ["monthly", "weekly", "daily"], "min": 2},
            "1Week": {"timeframes": ["monthly", "weekly"], "min": 1},
            "1Month": {"timeframes": ["monthly"], "min": 1},
        }

        req = requirements.get(detection_timeframe, requirements["1Day"])
        relevant_tfs = req["timeframes"]
        min_aligned = req["min"]

        # Filter TFC details to relevant timeframes
        relevant_details = [d for d in tfc.details if d.timeframe in relevant_tfs]

        # Count directional alignment in dominant direction
        if tfc.dominant_bias in ("bullish", "bearish"):
            aligned = [d for d in relevant_details if d.bias == tfc.dominant_bias]
        else:
            aligned = []

        effective_score = len(aligned)
        max_possible = len(relevant_tfs)
        passes = effective_score >= min_aligned

        # Quality grade for contextual score
        ratio = effective_score / max_possible if max_possible > 0 else 0
        if ratio >= 1.0:
            quality = "A+"
        elif ratio >= 0.75:
            quality = "A"
        elif ratio >= 0.5:
            quality = "B"
        elif ratio >= 0.25:
            quality = "C"
        else:
            quality = "D"

        return {
            "effective_score": effective_score,
            "max_possible": max_possible,
            "effective_quality": quality,
            "relevant_timeframes": relevant_tfs,
            "aligned_in_context": [d.timeframe for d in aligned],
            "passes": passes,
            "min_required": min_aligned
        }

    @staticmethod
    def detect_2_1_2_reversal(bars: List[Bar]) -> Optional[STRATPattern]:
        """
        Detect 2-1-2 reversal pattern (most reliable STRAT setup).
        Pattern: 2U/2D -> 1 -> 2U/2D (opposite direction).

        Current-actionable only: the breakout (bar 3) MUST be the last bar in
        the window. Stale patterns from earlier bars are not reported - a 2-1-2
        whose breakout fired N bars ago is no longer the current setup.
        """
        if len(bars) < 3:
            return None

        bar1, bar2, bar3 = bars[-3], bars[-2], bars[-1]

        # Bullish 2-1-2: 2D -> 1 -> 2U
        if bar1.bar_type == "2D" and bar2.bar_type == "1" and bar3.bar_type == "2U":
            return STRATPattern(
                pattern_type="2-1-2 Reversal",
                bars=[bar1, bar2, bar3],
                direction="bullish",
                confidence="high",
                description=f"Bullish 2-1-2: Reversal from 2D low ${bar1.low:.2f}; trigger at inside bar high ${bar2.high:.2f} + 0.01"
            )

        # Bearish 2-1-2: 2U -> 1 -> 2D
        if bar1.bar_type == "2U" and bar2.bar_type == "1" and bar3.bar_type == "2D":
            return STRATPattern(
                pattern_type="2-1-2 Reversal",
                bars=[bar1, bar2, bar3],
                direction="bearish",
                confidence="high",
                description=f"Bearish 2-1-2: Reversal from 2U high ${bar1.high:.2f}; trigger at inside bar low ${bar2.low:.2f} - 0.01"
            )

        return None

    @staticmethod
    def detect_2_1_setup(bars: List[Bar]) -> Optional[STRATPattern]:
        """
        Detect 2-1 Setup - a potential 2-1-2 pattern awaiting breakout.
        Pattern: 2U/2D -> 1 (last bar is inside bar, awaiting breakout)

        This is NOT a confirmed pattern - it's a setup awaiting confirmation.
        Reports the breakout levels to watch.
        """
        if len(bars) < 2:
            return None

        # Check the LAST 2 bars only - this is a current setup
        bar1, bar2 = bars[-2], bars[-1]

        # Only valid if the current (last) bar is an inside bar (Type 1)
        if bar2.bar_type != "1":
            return None

        # Bullish setup: 2D -> 1 (awaiting breakout above inside bar high)
        if bar1.bar_type == "2D":
            return STRATPattern(
                pattern_type="2-1 Setup",
                bars=[bar1, bar2],
                direction="bullish",
                confidence="low",
                description=f"2-1 Setup (bullish potential): Awaiting breakout above ${bar2.high:.2f} for 2-1-2U or below ${bar2.low:.2f}"
            )

        # Bearish setup: 2U -> 1 (awaiting breakout below inside bar low)
        elif bar1.bar_type == "2U":
            return STRATPattern(
                pattern_type="2-1 Setup",
                bars=[bar1, bar2],
                direction="bearish",
                confidence="low",
                description=f"2-1 Setup (bearish potential): Awaiting breakout below ${bar2.low:.2f} for 2-1-2D or above ${bar2.high:.2f}"
            )

        return None

    @staticmethod
    def detect_3_1_2_continuation(bars: List[Bar]) -> Optional[STRATPattern]:
        """
        Detect 3-1-2 continuation pattern.
        Pattern: 3 (directional) -> 1 (inside) -> 2 (breakout in same direction).

        Current-actionable only: the breakout (bar 3) MUST be the last bar in
        the window.
        """
        if len(bars) < 3:
            return None

        bar1, bar2, bar3 = bars[-3], bars[-2], bars[-1]

        if bar1.bar_type != "3" or bar2.bar_type != "1":
            return None

        # Bullish continuation: 3 up -> 1 -> 2U
        if bar1.close > bar1.open and bar3.bar_type == "2U":
            return STRATPattern(
                pattern_type="3-1-2 Continuation",
                bars=[bar1, bar2, bar3],
                direction="bullish",
                confidence="high",
                description=f"Bullish 3-1-2: Trend continuation; trigger at inside bar high ${bar2.high:.2f} + 0.01"
            )

        # Bearish continuation: 3 down -> 1 -> 2D
        if bar1.close < bar1.open and bar3.bar_type == "2D":
            return STRATPattern(
                pattern_type="3-1-2 Continuation",
                bars=[bar1, bar2, bar3],
                direction="bearish",
                confidence="high",
                description=f"Bearish 3-1-2: Trend continuation; trigger at inside bar low ${bar2.low:.2f} - 0.01"
            )

        return None

    @staticmethod
    def detect_3_1_setup(bars: List[Bar]) -> Optional[STRATPattern]:
        """
        Detect 3-1 Setup - a potential 3-1-2 pattern awaiting breakout.
        Pattern: 3 -> 1 (last bar is inside bar, awaiting breakout)

        This is NOT a confirmed pattern - it's a setup awaiting confirmation.
        """
        if len(bars) < 2:
            return None

        # Check the LAST 2 bars only - this is a current setup
        bar1, bar2 = bars[-2], bars[-1]

        # Only valid if the current (last) bar is an inside bar (Type 1)
        if bar2.bar_type != "1" or bar1.bar_type != "3":
            return None

        # Bullish setup: 3 up -> 1 (awaiting breakout above inside bar high)
        if bar1.close > bar1.open:
            return STRATPattern(
                pattern_type="3-1 Setup",
                bars=[bar1, bar2],
                direction="bullish",
                confidence="low",
                description=f"3-1 Setup (bullish): Awaiting breakout above ${bar2.high:.2f} for 3-1-2U continuation"
            )

        # Bearish setup: 3 down -> 1 (awaiting breakout below inside bar low)
        elif bar1.close < bar1.open:
            return STRATPattern(
                pattern_type="3-1 Setup",
                bars=[bar1, bar2],
                direction="bearish",
                confidence="low",
                description=f"3-1 Setup (bearish): Awaiting breakout below ${bar2.low:.2f} for 3-1-2D continuation"
            )

        return None

    @staticmethod
    def detect_2_2_reversal(bars: List[Bar]) -> Optional[STRATPattern]:
        """
        Detect 2-2 Reversal pattern (actionable entry signal).
        Pattern: 2D -> 2U (bullish reversal) or 2U -> 2D (bearish reversal).

        Current-actionable only: the reversal bar (bar 2) MUST be the last bar
        in the window. A 2-2 reversal whose flip fired N bars ago is no longer
        the current setup - by definition something else has happened since.
        """
        if len(bars) < 2:
            return None

        bar1, bar2 = bars[-2], bars[-1]

        # Bullish 2-2 Reversal: 2D -> 2U
        if bar1.bar_type == "2D" and bar2.bar_type == "2U":
            return STRATPattern(
                pattern_type="2-2 Reversal",
                bars=[bar1, bar2],
                direction="bullish",
                confidence="medium",
                description=f"Bullish 2-2 Reversal: 2D to 2U flip; trigger at reference bar (2D) high ${bar1.high:.2f} + 0.01"
            )

        # Bearish 2-2 Reversal: 2U -> 2D
        if bar1.bar_type == "2U" and bar2.bar_type == "2D":
            return STRATPattern(
                pattern_type="2-2 Reversal",
                bars=[bar1, bar2],
                direction="bearish",
                confidence="medium",
                description=f"Bearish 2-2 Reversal: 2U to 2D flip; trigger at reference bar (2U) low ${bar1.low:.2f} - 0.01"
            )

        return None

    @staticmethod
    def detect_2_2_continuation(bars: List[Bar]) -> Optional[STRATPattern]:
        """
        Detect 2-2 Continuation pattern.

        Per methodology this is position management state, NOT a new entry
        signal (see strat-methodology/SKILL.md: "Continuation is Deferred").
        Excluded from scan_for_patterns default output. Function preserved
        because future internal logic (trailing stop confirmation, exit
        timing) may consume it.

        Current-actionable only: the continuation bar (bar 2) MUST be the
        last bar in the window.
        """
        if len(bars) < 2:
            return None

        bar1, bar2 = bars[-2], bars[-1]

        # Two consecutive 2U (bullish continuation)
        if bar1.bar_type == "2U" and bar2.bar_type == "2U":
            return STRATPattern(
                pattern_type="2-2 Continuation",
                bars=[bar1, bar2],
                direction="bullish",
                confidence="low",
                description=f"Bullish 2-2 Continuation: Momentum to ${bar2.high:.2f} (not entry signal, watch for exhaustion)"
            )

        # Two consecutive 2D (bearish continuation)
        if bar1.bar_type == "2D" and bar2.bar_type == "2D":
            return STRATPattern(
                pattern_type="2-2 Continuation",
                bars=[bar1, bar2],
                direction="bearish",
                confidence="low",
                description=f"Bearish 2-2 Continuation: Momentum to ${bar2.low:.2f} (not entry signal, watch for exhaustion)"
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
        prev_bar = bars[-2]

        # Current bar is inside bar
        if last_bar.bar_type == "1":
            # Determine likely direction based on prior trend
            prior_trend = "bullish" if prev_bar.close > prev_bar.open else "bearish"

            return STRATPattern(
                pattern_type="Inside Bar Setup",
                bars=[prev_bar, last_bar],
                direction=prior_trend,
                confidence="low",
                description=f"Inside bar at ${last_bar.close:.2f} - Watch for breakout (High: ${last_bar.high:.2f}, Low: ${last_bar.low:.2f})"
            )

        return None

    @staticmethod
    def scan_for_patterns(bars: List[Dict], timeframe: str = "1Day") -> List[STRATPattern]:
        """
        Scan bar data for currently-actionable STRAT patterns.

        Only patterns whose confirming bar is the LAST bar in the window are
        returned. Stale patterns (confirmed by an earlier bar in the window)
        are filtered out, because subsequent bar action has already moved the
        market past the original signal.

        Setups (2-1, 3-1, inside bar) are reported only when no confirmed
        pattern exists - if a confirmed pattern just fired, the setup state
        is no longer the relevant trade context.

        2-2 Continuation is intentionally not surfaced here: per methodology
        it is position management, not a new entry signal. The detector is
        still available for downstream code that needs it.

        Sort order is confidence-desc. Recency is implicitly equal across all
        returned patterns (they all share the same confirming bar, the last
        bar in the window).
        """
        if len(bars) < 2:
            return []

        classified_bars = STRATDetector.classify_bars(bars, timeframe)

        confirmed: List[STRATPattern] = []

        pattern_2_1_2 = STRATDetector.detect_2_1_2_reversal(classified_bars)
        if pattern_2_1_2:
            confirmed.append(pattern_2_1_2)

        pattern_3_1_2 = STRATDetector.detect_3_1_2_continuation(classified_bars)
        if pattern_3_1_2:
            confirmed.append(pattern_3_1_2)

        pattern_2_2_rev = STRATDetector.detect_2_2_reversal(classified_bars)
        if pattern_2_2_rev:
            confirmed.append(pattern_2_2_rev)

        # Setups only if no confirmed pattern exists (per the comment that
        # was here previously - this loop honors it now).
        setups: List[STRATPattern] = []
        if not confirmed:
            setup_2_1 = STRATDetector.detect_2_1_setup(classified_bars)
            if setup_2_1:
                setups.append(setup_2_1)

            setup_3_1 = STRATDetector.detect_3_1_setup(classified_bars)
            if setup_3_1:
                setups.append(setup_3_1)

            # Generic inside-bar setup only if no specific setup matched
            if not setups:
                inside_bar = STRATDetector.detect_inside_bar_setup(classified_bars)
                if inside_bar:
                    setups.append(inside_bar)

        patterns = confirmed + setups
        confidence_order = {"high": 3, "medium": 2, "low": 1}
        patterns.sort(key=lambda p: confidence_order[p.confidence], reverse=True)
        return patterns


def format_pattern_report(ticker: str, patterns: List[STRATPattern], current_price: float, metrics: Optional[StockMetrics] = None) -> str:
    """Format detected patterns into readable report"""
    if not patterns:
        return f"**{ticker}**: No STRAT patterns detected"

    report = f"**{ticker}** - ${current_price:.2f}\n"

    if metrics:
        report += f"Metrics: {metrics}\n"

    for pattern in patterns:
        direction_label = "[BULLISH]" if pattern.direction == "bullish" else "[BEARISH]"
        confirmed_at = pattern.timestamp.split("T")[0] if "T" in pattern.timestamp else pattern.timestamp
        report += f"{direction_label} **{pattern.pattern_type}** ({pattern.confidence} confidence)\n"
        report += f"   {pattern.description}\n"
        report += f"   Confirmed on: {confirmed_at}\n"
        report += f"   Entry: ${pattern.entry_level:.2f}\n"

    return report


def format_tfc_report(ticker: str, tfc: TFCScore, metrics: Optional[StockMetrics] = None) -> str:
    """Format TFC analysis into readable report"""
    report = f"**{ticker}** - {tfc}\n"

    if metrics:
        report += f"Metrics: {metrics}\n"

    report += "\n**Timeframe Breakdown:**\n"
    report += f"Directional Split: {tfc.bullish_count} Bullish / {tfc.bearish_count} Bearish / {tfc.neutral_count} Neutral\n\n"
    for detail in tfc.details:
        bias_indicator = "[BULL]" if detail.bias == "bullish" else "[BEAR]" if detail.bias == "bearish" else "[NEUT]"
        pattern_str = f" ({detail.pattern})" if detail.pattern else ""
        forming_str = " (forming)" if detail.is_forming else ""
        # Type 1 bars are neutral/indecision - indicate this in output
        type_note = " - indecision" if detail.bar_type == "1" else ""
        report += f"  {bias_indicator} {detail.timeframe.upper()}: {detail.bias}{pattern_str} - Type {detail.bar_type}{forming_str}{type_note}\n"

    return report
