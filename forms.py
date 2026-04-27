"""
WTForms definitions used by the Flask web interface.

This module only defines user input forms.
It does NOT contain any business logic, indicator logic, or IBKR logic.

Important:
- Field names are tightly coupled with the existing backend logic.
- Do NOT rename any fields unless the backend is updated accordingly.
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    IntegerField,
    DecimalField,
    SelectField,
    BooleanField,
    RadioField,
    FloatField,
)
from wtforms.validators import DataRequired


# ---------------------------------------------------------------------------
# Authentication form
# ---------------------------------------------------------------------------

class LoginForm(FlaskForm):
    """
    Simple login form.

    Currently used only for UI authentication (if enabled).
    """

    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


# ---------------------------------------------------------------------------
# Main indicator / screening configuration form
# ---------------------------------------------------------------------------

class Parameters(FlaskForm):
    """
    Main form that represents the full indicator and comparison configuration.

    Each field here is consumed directly by the backend logic
    (IBapi / BuySellSignal).

    IMPORTANT:
    Field names and option values are relied upon by the existing code.
    """

    # ------------------------------------------------------------------
    # Indicator parameters
    # ------------------------------------------------------------------

    FastSMA = IntegerField("Fast SMA")
    MediumSMA = IntegerField("Medium SMA")
    SlowSMA = IntegerField("Slow SMA")
    VWAP = IntegerField("VWAP")
    RSI = IntegerField("RSI")
    FastEMA = IntegerField("Fast EMA")
    SlowEMA = IntegerField("Slow EMA")
    OBV = IntegerField("OBV")
    ATR = IntegerField("ATR")

    PrevClose = IntegerField("Previous Close")
    LowOfDay = IntegerField("Low of Day")
    HighOfDay = IntegerField("High of Day")

    # ------------------------------------------------------------------
    # Percentage / threshold values for indicators
    # ------------------------------------------------------------------

    PercentageVWAP = DecimalField("Percentage VWAP")
    PercentageFastSMA = DecimalField("Percentage Fast SMA")
    PercentageMediumSMA = DecimalField("Percentage Medium SMA")
    PercentageSlowSMA = DecimalField("Percentage Slow SMA")
    PercentageRSI = DecimalField("Percentage RSI")
    PercentageFastEMA = DecimalField("Percentage Fast EMA")
    PercentageSlowEMA = DecimalField("Percentage Slow EMA")
    PercentageOBV = DecimalField("Percentage OBV")
    PercentageATR = DecimalField("Percentage ATR")

    PercentagePrevClose = DecimalField("Percentage Previous Close")
    PercentagePrevClose1 = DecimalField("Percentage Previous Close1")
    PercentageLowOfDay = DecimalField("Percentage Low Of Day")
    PercentageLowOfDay1 = DecimalField("Percentage Low Of Day1")
    PercentageHighOfDay = DecimalField("Percentage High Of Day")
    PercentageHighOfDay1 = DecimalField("Percentage High Of Day1")

    # ------------------------------------------------------------------
    # Comparison operators for indicators
    # ------------------------------------------------------------------

    _STANDARD_COMPARISON_CHOICES = [
        ("greater", ">"),
        ("greaterEqual", ">="),
        ("lower", "<"),
        ("lowerEqual", "<="),
        ("between", "between"),
        ("withinPercentAbove", "Within % Above"),
        ("withinPercentBelow", "Within % Below"),
        ("withinPercentEither", "Within Either %"),
        ("Not used", "disabled"),
    ]

    TIMEFRAME_CHOICES = [
        ("1 min", "1 min"),
        ("2 min", "2 min"),
        ("5 min", "5 min"),
        ("15 min", "15 min"),
        ("1 hour", "1 hour"),
        ("1 day", "1 day"),
        ("1 week", "1 week"),
        ("1 month", "1 month"),
    ]

    ComparisonFastSMA = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonMediumSMA = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonSlowSMA = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonVWAP = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonRSI = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonFastEMA = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonSlowEMA = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonOBV = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonATR = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonPrevClose = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonLowOfDay = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonHighOfDay = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    # ------------------------------------------------------------------
    # Enable / disable indicators
    # ------------------------------------------------------------------

    booleanFastSMA = BooleanField(
        "Add Indicator",
        false_values=(False, "false", 0, "0"),
    )
    booleanMediumSMA = BooleanField(
        "Add Indicator",
        false_values=(False, "false", 0, "0"),
    )
    booleanSlowSMA = BooleanField(
        "Add Indicator",
        false_values=(False, "false", 0, "0"),
    )
    booleanVWAP = BooleanField("Add Indicator")
    booleanRSI = BooleanField("Add Indicator")
    booleanFastEMA = BooleanField("Add Indicator")
    booleanSlowEMA = BooleanField("Add Indicator")
    booleanOBV = BooleanField("Add Indicator")
    booleanATR = BooleanField("Add Indicator")

    booleanPrevClose = BooleanField("Add Indicator")
    booleanLowOfDay = BooleanField("Add Indicator")
    booleanHighOfDay = BooleanField("Add Indicator")

    # ------------------------------------------------------------------
    # Pivot points configuration
    # ------------------------------------------------------------------

    PivotPoint = SelectField(
        "Programming Language",
        choices=[
            ("PP", "Pivot Point"),
            ("R1", "Resistance 1"),
            ("R2", "Resistance 2"),
            ("R3", "Resistance 3"),
            ("S1", "Support 1"),
            ("S2", "Support 2"),
            ("S3", "Support 3"),
            ("Not used", "disabled"),
        ],
    )

    PivotPoint1 = SelectField(
        "Programming Language",
        choices=[
            ("PP", "Pivot Point"),
            ("R1", "Resistance 1"),
            ("R2", "Resistance 2"),
            ("R3", "Resistance 3"),
            ("S1", "Support 1"),
            ("S2", "Support 2"),
            ("S3", "Support 3"),
            ("Not used", "disabled"),
        ],
    )

    PivotPoint2 = SelectField(
        "Programming Language",
        choices=[
            ("PP", "Pivot Point"),
            ("R1", "Resistance 1"),
            ("R2", "Resistance 2"),
            ("R3", "Resistance 3"),
            ("S1", "Support 1"),
            ("S2", "Support 2"),
            ("S3", "Support 3"),
            ("Not used", "disabled"),
        ],
    )

    PivotPoint3 = SelectField(
        "Programming Language",
        choices=[
            ("PP", "Pivot Point"),
            ("R1", "Resistance 1"),
            ("R2", "Resistance 2"),
            ("R3", "Resistance 3"),
            ("S1", "Support 1"),
            ("S2", "Support 2"),
            ("S3", "Support 3"),
            ("Not used", "disabled"),
        ],
    )

    _CROSS_SMA_COMPARISON_CHOICES = [
        ("greater", ">"),
        ("greaterEqual", ">="),
        ("lower", "<"),
        ("lowerEqual", "<="),
        ("between", "between"),
        ("crossAbove", "Cross Above"),
        ("crossBelow", "Cross Below"),
        ("withinPercentAbove", "Within % Above"),
        ("withinPercentBelow", "Within % Below"),
        ("withinPercentEither", "Within Either %"),
        ("Not used", "disabled"),
    ]

    Cross200SMA = IntegerField("Cross 200 SMA")
    ComparisonCross200SMA = SelectField(
        "Cross 200 SMA",
        choices=_CROSS_SMA_COMPARISON_CHOICES,
    )
    PercentageCross200SMA = DecimalField("% from 200 SMA")
    Cross200SMABool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="percentage",
    )

    Cross50SMA = IntegerField("Cross 50 SMA")
    ComparisonCross50SMA = SelectField(
        "Cross 50 SMA",
        choices=_CROSS_SMA_COMPARISON_CHOICES,
    )
    PercentageCross50SMA = DecimalField("% from 50 SMA")
    Cross50SMABool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="percentage",
    )

    # ------------------------------------------------------------------
    # Break High (recent X-day high)
    # ------------------------------------------------------------------

    BreakHigh = IntegerField("Break High Days")
    PercentageBreakHigh = DecimalField("Percentage Break High")

    ComparisonBreakHigh = SelectField(
        "Break High",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    BreakHighBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="percentage",
    )

    # ------------------------------------------------------------------
    # Pullback Retracement (% retracement of day's move)
    # ------------------------------------------------------------------

    PullbackPct = IntegerField("Pullback Retracement")
    PercentagePullbackPct = DecimalField("Pullback Retracement %")
    PercentagePullbackPct1 = DecimalField("Pullback Retracement %1")

    ComparisonPullbackPct = SelectField(
        "Pullback Retracement",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    # ------------------------------------------------------------------
    # 2nd Pullback Retracement
    # ------------------------------------------------------------------

    PullbackPct2 = IntegerField("2nd Pullback Retracement")
    PercentagePullbackPct2 = DecimalField("2nd Pullback Retracement %")
    PercentagePullbackPct2_1 = DecimalField("2nd Pullback Retracement %1")

    ComparisonPullbackPct2 = SelectField(
        "2nd Pullback Retracement",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    # ------------------------------------------------------------------
    # Fibonacci Pullback (retracement levels on intraday/session moves)
    # ------------------------------------------------------------------
    # Fibonacci pullback checks if price is near Fib retracement levels
    # of the move from previous close to session high
    # Can select specific Fib level (38.2%, 50%, 61.8%, 78.6%)
    # and tolerance percentage

    FibPullbackLevel = SelectField(
        "Fib Level",
        choices=[
            ("38.2", "38.2%"),
            ("50.0", "50.0%"),
            ("61.8", "61.8%"),
            ("78.6", "78.6%"),
        ],
        default="61.8",
    )

    FibPullback = DecimalField("Fib Pullback Tolerance %")
    PercentageFibPullback = DecimalField("Fib Pullback Within %")
    PercentageFibPullback1 = DecimalField("Fib Pullback Within %1")

    ComparisonFibPullback = SelectField(
        "Fib Pullback",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    FibPullback_tf = SelectField(
        "Fib Pullback TF",
        choices=TIMEFRAME_CHOICES,
        default="1 day",
    )

    # ------------------------------------------------------------------
    # Gap Pullback (intraday pullback to overnight gap Fib levels)
    # ------------------------------------------------------------------
    # Gap Pullback checks if intraday price is near Fib retracement levels
    # of the overnight gap (open - previous close)
    # Can select specific Fib level (38.2%, 50%, 61.8%, 78.6%)
    # and tolerance percentage
    #
    # Example: If a stock gaps up 10%, the 50% Fibonacci level would be at 5%
    # A "50% pullback" means price has pulled back 50% of the gap size
    # 
    # Use this to find stocks that gapped and are now at key pullback levels:
    # - 38.2%: Shallow pullback, strong momentum continuation likely
    # - 50%: Mid-level pullback, balanced risk/reward
    # - 61.8%: Deep pullback, potential reversal area or strong support
    # - 78.6%: Near-complete pullback, major support/resistance

    GapPullbackLevel = SelectField(
        "Gap Level",
        choices=[
            ("38.2", "38.2% (Shallow)"),
            ("50.0", "50.0% (Mid)"),
            ("61.8", "61.8% (Deep)"),
            ("78.6", "78.6% (Full)"),
        ],
        default="61.8",
    )

    GapPullback = DecimalField(
        "Gap Pullback Tolerance %",
        render_kw={
            "title": "Tolerance percentage above/below the target Fib level",
            "placeholder": "e.g., 0.5 for ±0.5% tolerance"
        }
    )
    PercentageGapPullback = DecimalField("Gap Pullback Within %")
    PercentageGapPullback1 = DecimalField("Gap Pullback Within %1")

    ComparisonGapPullback = SelectField(
        "Gap Pullback",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    GapPullback_tf = SelectField(
        "Gap Pullback TF",
        choices=TIMEFRAME_CHOICES,
        default="1 min",
    )

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Up Gap (daily gap up from previous close 9:30 AM - 4 PM EST)
    # ------------------------------------------------------------------
    # WHAT IS A GAP UP?
    # A gap up occurs when today's opening price is HIGHER than yesterday's
    # closing price. This happens when significant news/events occur after 
    # hours, causing the stock to open at a higher price.
    #
    # WHAT THE "GAP %" SHOWS:
    # The percentage increase from yesterday's close to today's open.
    # Example: If yesterday closed at $100 and today opened at $103, 
    #          that's a 3% gap up.
    #
    # IS THE GAP CLOSED?
    # A gap is considered CLOSED when price returns to yesterday's close level.
    # If stock gapped up to $103 but then drops back below $100 (yesterday's close),
    # the gap has been filled/closed.
    #
    # USE THIS TO FIND:
    # - Bullish stocks with strong overnight demand (gap-up plays)
    # - Stocks showing strength that may continue upward
    # - Potential pullback entry points (when gap closes)

    UpGap = IntegerField(
        "Up Gap %",
        render_kw={
            "title": "Minimum gap up percentage to find (e.g., 3 for 3% gap up)",
            "placeholder": "Enter minimum % gap"
        }
    )
    PercentageUpGap = DecimalField("Up Gap %")
    PercentageUpGap1 = DecimalField("Up Gap %1")

    ComparisonUpGap = SelectField(
        "Up Gap",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    # ------------------------------------------------------------------
    # Down Gap (daily gap down from previous close 9:30 AM - 4 PM EST)
    # ------------------------------------------------------------------
    # WHAT IS A GAP DOWN?
    # A gap down occurs when today's opening price is LOWER than yesterday's
    # closing price. This happens when negative news/events occur after hours,
    # causing the stock to open at a lower price.
    #
    # WHAT THE "GAP %" SHOWS:
    # The percentage decrease from yesterday's close to today's open.
    # Example: If yesterday closed at $100 and today opened at $97,
    #          that's a 3% gap down.
    #
    # IS THE GAP CLOSED?
    # A gap is considered CLOSED when price returns to yesterday's close level.
    # If stock gapped down to $97 but then rises back above $100 (yesterday's close),
    # the gap has been filled/closed.
    #
    # USE THIS TO FIND:
    # - Bearish stocks with weakness from overnight news (gap-down plays)
    # - Short opportunities or potential reversal trades
    # - Support levels at yesterday's close (where gap would fill)

    DownGap = IntegerField(
        "Down Gap %",
        render_kw={
            "title": "Minimum gap down percentage to find (e.g., 3 for 3% gap down)",
            "placeholder": "Enter minimum % gap"
        }
    )
    PercentageDownGap = DecimalField("Down Gap %")
    PercentageDownGap1 = DecimalField("Down Gap %1")

    ComparisonDownGap = SelectField(
        "Down Gap",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    # Fibonacci Gap (daily gap vs Fib retracement levels)
    # ------------------------------------------------------------------

    FibGap = IntegerField("Fibonacci Gap")
    PercentageFibGap = DecimalField("Fibonacci Gap %")
    PercentageFibGap1 = DecimalField("Fibonacci Gap %1")

    ComparisonFibGap = SelectField(
        "Fibonacci Gap",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    ComparisonPivotPoint = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )
    ComparisonPivotPoint2 = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )
    ComparisonPivotPoint3 = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    PercentagePivotPoint = DecimalField("Percentage PivotPoint")
    PercentagePivotPoint1 = DecimalField("Percentage PivotPoint1")
    PercentagePivotPoint2 = DecimalField("Percentage PivotPoint2")
    PercentagePivotPoint3 = DecimalField("Percentage PivotPoint3")

    # ------------------------------------------------------------------
    # Global time frame selector (renamed label)
    # ------------------------------------------------------------------
    addFrequency = SelectField(
        "Time Frame",
        choices=TIMEFRAME_CHOICES,
    )

    # ------------------------------------------------------------------
    # Extended Hours / After-Hours Trading Configuration
    # ------------------------------------------------------------------
    EnableExtendedHours = BooleanField(
        "Enable Extended Hours Trading (Pre-Market + After-Hours)",
        default=False,
        render_kw={
            "title": "Include pre-market (4am-9:30am ET) and after-hours (4pm-8pm ET) data in analysis. "
                     "Extended hours: 4pm-8pm ET. Overnight: 8pm ET - 4am ET next day"
        }
    )

    IncludeOvernightData = BooleanField(
        "Include Overnight Data (8pm-4am ET)",
        default=False,
        render_kw={
            "title": "Include overnight trading data from 8pm Eastern to 4am Eastern (next day). "
                     "Some stocks trade actively during these hours in after-hours market"
        }
    )

    ExtendedHoursVolumeWeight = DecimalField(
        "Extended Hours Volume Weight",
        default=1.0,
        render_kw={
            "title": "Multiplier for volume calculations during extended hours (1.0 = same as regular hours, 0.5 = half weight)",
            "min": 0.1, "max": 2.0, "step": 0.1
        }
    )

    # ------------------------------------------------------------------
    # Per-indicator time-frame selectors (new)
    # ------------------------------------------------------------------
    FastSMA_tf = SelectField("Fast SMA Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    FastSMA1_tf = SelectField("Fast SMA1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    MediumSMA_tf = SelectField("Medium SMA Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    MediumSMA1_tf = SelectField("Medium SMA1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    SlowSMA_tf = SelectField("Slow SMA Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    SlowSMA1_tf = SelectField("Slow SMA1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    VWAP_tf = SelectField("VWAP Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    VWAP1_tf = SelectField("VWAP1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    RSI_tf = SelectField("RSI Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    RSI1_tf = SelectField("RSI1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    FastEMA_tf = SelectField("Fast EMA Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    FastEMA1_tf = SelectField("Fast EMA1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    SlowEMA_tf = SelectField("Slow EMA Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    SlowEMA1_tf = SelectField("Slow EMA1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    OBV_tf = SelectField("OBV Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    OBV1_tf = SelectField("OBV1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    ATR_tf = SelectField("ATR Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    ATR1_tf = SelectField("ATR1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")

    PrevClose_tf = SelectField("Previous Close Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    PrevClose1_tf = SelectField("Previous Close1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    LowOfDay_tf = SelectField("Low Of Day Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    LowOfDay1_tf = SelectField("Low Of Day1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    HighOfDay_tf = SelectField("High Of Day Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    HighOfDay1_tf = SelectField("High Of Day1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")

    Volume_tf = SelectField("Volume Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    Volume1_tf = SelectField("Volume1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    averageVolume_tf = SelectField("Average Volume Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    averageVolume1_tf = SelectField("Average Volume1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    relativeVolume_tf = SelectField("Relative Volume Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    relativeVolume1_tf = SelectField("Relative Volume1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")

    Cross50SMA_tf = SelectField("Cross 50 SMA Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    Cross200SMA_tf = SelectField("Cross 200 SMA Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")

    BreakHigh_tf = SelectField("Break High Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    PullbackPct_tf = SelectField("Pullback Retracement Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    PullbackPct2_tf = SelectField("2nd Pullback Retracement Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    UpGap_tf = SelectField("Up Gap Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    DownGap_tf = SelectField("Down Gap Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    FibGap_tf = SelectField("Fibonacci Gap Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    Pivot_tf = SelectField("Pivot Point Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    Pivot_tf2 = SelectField("Pivot 2 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    Pivot_tf3 = SelectField("Pivot 3 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")

    # ------------------------------------------------------------------
    # Price level comparisons
    # ------------------------------------------------------------------

    Pricelevel = SelectField(
        "Price Level",
        choices=[
            ("pricelow", "price"),
        ],
    )

    Pricelevel1 = SelectField(
        "Price Upper L",
        choices=[
            ("pricehigh", "price"),
        ],
    )

    ComparisonPrice = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    PercentagePrice = DecimalField("Percentage Price")
    PercentagePrice1 = DecimalField("Percentage Price")

    # ------------------------------------------------------------------
    # Average volume configuration
    # ------------------------------------------------------------------

    Volume = IntegerField("Volume")
    PercentageVolume = DecimalField("Percentage Volume")

    ComparisonVolume = SelectField(
        "Volume",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    AverageVolume = IntegerField("Average Volume")
    PercentageAverageVolume = DecimalField("Percentage Average Volume")

    ComparisonAverageVolume = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    # ------------------------------------------------------------------
    # Relative volume configuration
    # ------------------------------------------------------------------

    RelativeVolume = IntegerField("Relative Volume")
    PercentageRelativeVolume = DecimalField("Percentage Relative Volume")

    ComparisonRelativeVolume = SelectField(
        "Programming Language",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    # ------------------------------------------------------------------
    # Market Cap (in millions, from IBKR fundamental ratios)
    # ------------------------------------------------------------------

    MarketCap = IntegerField("Market Cap")
    PercentageMarketCap = DecimalField("Market Cap Threshold")
    PercentageMarketCap1 = DecimalField("Market Cap Threshold1")

    ComparisonMarketCap = SelectField(
        "Market Cap",
        choices=_STANDARD_COMPARISON_CHOICES,
        default="Not used",
    )

    # ------------------------------------------------------------------
    # Percentage / absolute value selector for each indicator
    # ------------------------------------------------------------------

    SMAFastBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    SMAMediumBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    smaslowyesno = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    rsiyesno = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    VWAPBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    FastEMABool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    SlowEMABool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    OBVBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    ATRBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    PrevCloseBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    LowOfDayBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    HighOfDayBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    pivotPointBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    priceyesno = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    VolumeBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    averageVolumeBool = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    relativeVolumeyesno = RadioField(
        "",
        choices=[("percentage", "%"), ("value", "val")],
        default="value",
    )

    # ------------------------------------------------------------------
    # Price reference selector (current vs previous close)
    # ------------------------------------------------------------------

    CloseBool = RadioField(
        "",
        choices=[
            ("Close", "Current Price"),
            ("Previous Close", "Previous Close"),
        ],
        default="Close",
    )

    # ------------------------------------------------------------------
    # News headlines
    # ------------------------------------------------------------------

    ComparisonNews = SelectField(
        "News",
        choices=[
            ("Not used", "disabled"),
            ("Used", "enabled"),
        ],
    )

    NewsMaxHeadlines = IntegerField("Max Headlines")
    NewsWithinHours = IntegerField("News Within Hours")
    NewsWithinValue = IntegerField("News Within Value")
    NewsTimeUnit = SelectField(
        "Time Unit",
        choices=[
            ("minutes", "Minutes"),
            ("hours", "Hours"),
            ("days", "Days"),
        ],
        default="minutes",
    )
    NewsExcludePublishers = StringField("Exclude Publishers")
    NewsKeywords = StringField("News Keywords")
    NewsReadAloud = SelectField(
        "Read Headlines Aloud",
        choices=[
            ("off", "Off"),
            ("on", "On"),
        ],
        default="off",
    )
    # Read Headlines Aloud time window configuration
    NewsReadAloudWithinValue = IntegerField(
        "Read Aloud Within (0=all)",
        default=0,
        render_kw={"title": "Time window for reading headlines aloud (0 = read all headlines)"}
    )
    NewsReadAloudTimeUnit = SelectField(
        "Time Unit",
        choices=[
            ("minutes", "Minutes"),
            ("hours", "Hours"),
            ("days", "Days"),
        ],
        default="minutes",
    )
    NewsAutoReadAll = SelectField(
        "Auto-Read All News",
        choices=[
            ("off", "Off"),
            ("on", "On"),
        ],
        default="off",
        render_kw={"title": "Automatically read all news headlines aloud after results are returned"}
    )

    # News provider selection
    NewsProviders = StringField(
        "Preferred News Providers",
        default="",
        render_kw={
            "placeholder": "e.g. BZ, FLY, DJNL, DJ-N, MT, GS (leave blank for all)",
            "title": "Comma-separated provider codes to include. Leave blank to use all subscribed providers."
        }
    )

    # ------------------------------------------------------------------
    # Gap Detection Configuration
    # ------------------------------------------------------------------
    
    GapDetectionEnabled = BooleanField(
        "Enable Gap Detection",
        default=False,
        render_kw={"title": "Scan for open/unfilled gaps"}
    )
    
    GapLookbackDays = IntegerField(
        "Gap Lookback Period (days)",
        default=60,
        render_kw={"title": "Number of days to look back for gaps", "min": 5, "max": 252}
    )
    
    GapMinimumPercent = FloatField(
        "Minimum Gap Size (%)",
        default=2.0,
        render_kw={"title": "Only track gaps larger than this %", "min": 0.1, "max": 20.0, "step": 0.1}
    )
    
    GapProximityPercent = FloatField(
        "Gap Closing Proximity (%)",
        default=50.0,
        render_kw={"title": "Alert when within X% of filling the gap", "min": 10, "max": 100, "step": 5}
    )
    
    GapDownsideAlertSound = BooleanField(
        "Alert on Downside Gap Approach",
        default=True,
        render_kw={"title": "Play sound when downside gap is being filled"}
    )

    # ------------------------------------------------------------------
    # Stock Exclusion List
    # ------------------------------------------------------------------
    
    ExcludeStocksList = StringField(
        "Exclude Stocks (comma-separated)",
        default="",
        render_kw={
            "placeholder": "e.g. XYZ, ABC, DEF (leave blank for none)",
            "title": "Comma-separated list of stock symbols to exclude from scans"
        }
    )
    
    EnableStockExclusion = BooleanField(
        "Enable Stock Exclusion",
        default=False,
        render_kw={"title": "Check to exclude the listed stocks from scanner"}
    )

    # ------------------------------------------------------------------
    # % Change and Volume Monitoring
    # ------------------------------------------------------------------
    
    EnablePctChangeMonitor = BooleanField(
        "Enable % Change Monitoring",
        default=False,
        render_kw={"title": "Monitor stocks by % price change over time period"}
    )
    
    PctChangeThreshold = FloatField(
        "% Change Threshold",
        default=3.0,
        render_kw={"title": "Alert on price changes above this % (e.g., 3.0 = 3%)", "min": 0.1, "max": 50.0, "step": 0.1}
    )
    
    PctChangeLookbackMinutes = IntegerField(
        "Lookback Period (minutes)",
        default=5,
        render_kw={"title": "Check % change over last X minutes", "min": 1, "max": 1440}
    )
    
    EnablePctChangeTTS = BooleanField(
        "Read Alert on % Change",
        default=True,
        render_kw={"title": "Read stock name when price change exceeds threshold"}
    )
    
    EnableVolumeMonitor = BooleanField(
        "Enable Volume Monitoring",
        default=False,
        render_kw={"title": "Monitor stocks by volume over time period"}
    )
    
    VolumeLookbackMinutes = IntegerField(
        "Volume Lookback (minutes)",
        default=5,
        render_kw={"title": "Calculate volume for last X minutes", "min": 1, "max": 1440}
    )
    
    VolumeThreshold = IntegerField(
        "Volume Threshold (min)",
        default=50000,
        render_kw={"title": "Alert when volume in period exceeds this amount", "min": 1000}
    )
    
    EnableVolumeTTS = BooleanField(
        "Read Alert on Volume Spike",
        default=True,
        render_kw={"title": "Read stock name when volume exceeds threshold"}
    )
    
    EnableKeyLevelDetection = BooleanField(
        "Enable Key Level Detection",
        default=False,
        render_kw={"title": "Highlight stocks near key support/resistance/pivot levels"}
    )
    
    KeyLevelProximityPercent = FloatField(
        "Key Level Proximity %",
        default=1.0,
        render_kw={"title": "Highlight when within X% of key level", "min": 0.1, "max": 5.0, "step": 0.1}
    )
    
    PlayKeyLevelSound = BooleanField(
        "Play Sound on Key Level Hit",
        default=True,
        render_kw={"title": "Play custom sound when stock approaches key level"}
    )

    # ------------------------------------------------------------------
    # 200 SMA BULLISH CROSSOVER DETECTION
    # ------------------------------------------------------------------
    
    Enable200SMABullishCrossover = BooleanField(
        "Enable 200 SMA Bullish Crossover Detection",
        default=False,
        render_kw={"title": "Detect when stock crosses above 200 SMA from below"}
    )
    
    EnableSMA200TTS = BooleanField(
        "Read Alert on 200 SMA Bullish Crossover",
        default=True,
        render_kw={"title": "Read stock name and indicator name when bullish 200 SMA crossover detected"}
    )

    # ------------------------------------------------------------------
    # ON BALANCE VOLUME (OBV) ANALYSIS
    # ------------------------------------------------------------------
    
    EnableOBVAnalysis = BooleanField(
        "Enable OBV Analysis",
        default=False,
        render_kw={"title": "Analyze On Balance Volume strength and trend"}
    )
    
    OBVTrendPeriod = IntegerField(
        "OBV Trend Period (bars)",
        default=20,
        render_kw={"title": "Lookback period for OBV trend analysis", "min": 5, "max": 200, "step": 5}
    )
    
    OBVMovingAveragePeriod = IntegerField(
        "OBV Moving Average Period",
        default=10,
        render_kw={"title": "Period for OBV moving average comparison", "min": 3, "max": 50, "step": 1}
    )
    
    OBVStrengthThreshold = FloatField(
        "OBV Strength Threshold (%)",
        default=15.0,
        render_kw={"title": "Minimum % change in OBV to consider 'strong'", "min": 1.0, "max": 100.0, "step": 1.0}
    )
    
    EnableOBVTTS = BooleanField(
        "Read Alert on Strong OBV Changes",
        default=True,
        render_kw={"title": "Read stock name when OBV shows strong rising/declining momentum"}
    )

    # ------------------------------------------------------------------
    # ETF processing mode
    # ------------------------------------------------------------------

    Procesetf = SelectField(
        "Programming Language",
        choices=[
            ("processall", "All etf"),
            ("processonebyone", "etf by etf"),
        ],
    )

    # ------------------------------------------------------------------
    # Result Filtering - Include only stocks meeting checked indicators
    # When a checkbox is enabled, only stocks where that indicator 
    # meets the configured condition will be returned.
    # Leave all unchecked to return all results (default behavior).
    # ------------------------------------------------------------------

    filterVWAP = BooleanField("Filter by VWAP", default=False)
    filterFastSMA = BooleanField("Filter by Fast SMA", default=False)
    filterMediumSMA = BooleanField("Filter by Medium SMA", default=False)
    filterSlowSMA = BooleanField("Filter by Slow SMA", default=False)
    filterRSI = BooleanField("Filter by RSI", default=False)
    filterFastEMA = BooleanField("Filter by Fast EMA", default=False)
    filterSlowEMA = BooleanField("Filter by Slow EMA", default=False)
    filterOBV = BooleanField("Filter by OBV", default=False)
    filterATR = BooleanField("Filter by ATR", default=False)
    filterAverageVolume = BooleanField("Filter by Average Volume", default=False)
    filterRelativeVolume = BooleanField("Filter by Relative Volume", default=False)
    filterPrevClose = BooleanField("Filter by Previous Close", default=False)
    filterLowOfDay = BooleanField("Filter by Low of Day", default=False)
    filterHighOfDay = BooleanField("Filter by High of Day", default=False)
    filterCross50SMA = BooleanField("Filter by Cross 50 SMA", default=False)
    filterCross200SMA = BooleanField("Filter by Cross 200 SMA", default=False)
    filterBreakHigh = BooleanField("Filter by Break High", default=False)
    filterPullbackPct = BooleanField("Filter by Pullback %", default=False)
    filterPullbackPct2 = BooleanField("Filter by Pullback % 2", default=False)
    filterFibPullback = BooleanField("Filter by Fib Pullback", default=False)
    filterGapPullback = BooleanField("Filter by Gap Pullback", default=False)
    filterPivotPoint = BooleanField("Filter by Pivot Point", default=False)
    filterUpGap = BooleanField("Filter by Up Gap", default=False)
    filterDownGap = BooleanField("Filter by Down Gap", default=False)
    filterNewsKeyword = BooleanField("Filter by News Keywords", default=False)
    filterMarketCap = BooleanField("Filter by Market Cap", default=False)
    filterVolume = BooleanField("Filter by Volume", default=False)

    submit = SubmitField("Submit")


# ---------------------------------------------------------------------------
# Bracket order form
# ---------------------------------------------------------------------------

class SecondSubmit(FlaskForm):
    """
    Form used for submitting bracket order parameters.
    """

    BH = IntegerField("Braket High", validators=[DataRequired()])
    BL = IntegerField("Braket Low", validators=[DataRequired()])
    submit = SubmitField("Submit")
