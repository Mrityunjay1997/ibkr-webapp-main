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
        choices=[],
        default="1 day",
    )

    # ------------------------------------------------------------------
    # Gap Pullback (intraday pullback to overnight gap Fib levels)
    # ------------------------------------------------------------------
    # Gap Pullback checks if intraday price is near Fib retracement levels
    # of the overnight gap (open - previous close)
    # Can select specific Fib level (38.2%, 50%, 61.8%, 78.6%)
    # and tolerance percentage

    GapPullbackLevel = SelectField(
        "Gap Level",
        choices=[
            ("38.2", "38.2%"),
            ("50.0", "50.0%"),
            ("61.8", "61.8%"),
            ("78.6", "78.6%"),
        ],
        default="61.8",
    )

    GapPullback = DecimalField("Gap Pullback Tolerance %")
    PercentageGapPullback = DecimalField("Gap Pullback Within %")
    PercentageGapPullback1 = DecimalField("Gap Pullback Within %1")

    ComparisonGapPullback = SelectField(
        "Gap Pullback",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    GapPullback_tf = SelectField(
        "Gap Pullback TF",
        choices=[],
        default="1 min",
    )

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Up Gap (daily gap up from previous close 9:30 AM - 4 PM EST)
    # ------------------------------------------------------------------
    # Measures how much a stock gaps UP from previous close as %
    # Perfect for finding gap-up plays that may pullback
    # Uses only regular trading hours (9:30 AM - 4 PM EST)

    UpGap = IntegerField("Up Gap")
    PercentageUpGap = DecimalField("Up Gap %")
    PercentageUpGap1 = DecimalField("Up Gap %1")

    ComparisonUpGap = SelectField(
        "Up Gap",
        choices=_STANDARD_COMPARISON_CHOICES,
    )

    # ------------------------------------------------------------------
    # Down Gap (daily gap down from previous close 9:30 AM - 4 PM EST)
    # ------------------------------------------------------------------
    # Measures how much a stock gaps DOWN from previous close as %
    # Perfect for finding gap-down stocks for reversal plays
    # Uses only regular trading hours (9:30 AM - 4 PM EST)

    DownGap = IntegerField("Down Gap")
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

    PercentagePivotPoint = DecimalField("Percentage PivotPoint")
    PercentagePivotPoint1 = DecimalField("Percentage PivotPoint1")

    # ------------------------------------------------------------------
    # Time frame choices (used by global and per-indicator selects)
    # ------------------------------------------------------------------
    TIMEFRAME_CHOICES = [
        ("1 min", "1 min"),
        ("2 min", "2 min"),
        ("5 min", "5 min"),
        ("15 min", "15 min"),
        ("1 hour", "1 hour"),
        ("1 day", "1 day"),
    ]

    # ------------------------------------------------------------------
    # Global time frame selector (renamed label)
    # ------------------------------------------------------------------
    addFrequency = SelectField(
        "Time Frame",
        choices=TIMEFRAME_CHOICES,
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
    NewsAutoReadAll = SelectField(
        "Auto-Read All News",
        choices=[
            ("off", "Off"),
            ("on", "On"),
        ],
        default="off",
        render_kw={"title": "Automatically read all news headlines aloud after results are returned"}
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
