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

    ComparisonFastSMA = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    ComparisonMediumSMA = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    ComparisonSlowSMA = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    ComparisonVWAP = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    ComparisonRSI = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    ComparisonFastEMA = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    ComparisonSlowEMA = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    ComparisonOBV = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    ComparisonATR = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    ComparisonPrevClose = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    ComparisonLowOfDay = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    ComparisonHighOfDay = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
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

    ComparisonPivotPoint = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
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

    averageVolume_tf = SelectField("Average Volume Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    averageVolume1_tf = SelectField("Average Volume1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    relativeVolume_tf = SelectField("Relative Volume Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")
    relativeVolume1_tf = SelectField("Relative Volume1 Time Frame", choices=TIMEFRAME_CHOICES, default="1 day")

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
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    PercentagePrice = DecimalField("Percentage Price")
    PercentagePrice1 = DecimalField("Percentage Price")

    # ------------------------------------------------------------------
    # Average volume configuration
    # ------------------------------------------------------------------

    AverageVolume = IntegerField("Average Volume")
    PercentageAverageVolume = DecimalField("Percentage Average Volume")

    ComparisonAverageVolume = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
    )

    # ------------------------------------------------------------------
    # Relative volume configuration
    # ------------------------------------------------------------------

    RelativeVolume = IntegerField("Relative Volume")
    PercentageRelativeVolume = DecimalField("Percentage Relative Volume")

    ComparisonRelativeVolume = SelectField(
        "Programming Language",
        choices=[
            ("greater", ">"),
            ("greaterEqual", ">="),
            ("lower", "<"),
            ("lowerEqual", "<="),
            ("between", "between"),
            ("Not used", "disabled"),
        ],
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
