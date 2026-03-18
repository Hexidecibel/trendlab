import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class ErrorResponse(BaseModel):
    """Structured error response with user-friendly messages."""

    detail: str
    hint: str | None = None
    error_code: str | None = None
    request_id: str | None = None


class DataPoint(BaseModel):
    date: datetime.date
    value: float


class TimeSeries(BaseModel):
    source: str
    query: str
    points: list[DataPoint]
    metadata: dict = Field(default_factory=dict)


class FormFieldOption(BaseModel):
    value: str
    label: str


class FormField(BaseModel):
    name: str
    label: str
    field_type: str  # "text", "select", "autocomplete"
    placeholder: str = ""
    options: list[FormFieldOption] = Field(default_factory=list)
    depends_on: str | None = None  # field name this depends on


class ResamplePeriod(BaseModel):
    """Custom resample period supported by an adapter."""

    value: str  # e.g. "mls_season"
    label: str  # e.g. "MLS Season"
    description: str = ""  # e.g. "Aggregate by MLS season (Feb-Nov)"


class DataSourceInfo(BaseModel):
    name: str
    description: str
    form_fields: list[FormField] = Field(default_factory=list)
    resample_periods: list[ResamplePeriod] = Field(default_factory=list)


class LookupItem(BaseModel):
    value: str
    label: str


# --- Phase 3: Analysis models ---


class MovingAverage(BaseModel):
    window: int
    values: list[DataPoint]


class TrendSignal(BaseModel):
    direction: str  # "rising", "falling", "stable"
    momentum: float
    acceleration: float
    moving_averages: list[MovingAverage]
    momentum_series: list[DataPoint]


class SeasonalityResult(BaseModel):
    detected: bool
    period_days: int | None
    strength: float | None
    autocorrelation: list[float]


class AnomalyPoint(BaseModel):
    date: datetime.date
    value: float
    score: float
    method: str


class AnomalyReport(BaseModel):
    method: str
    threshold: float
    anomalies: list[AnomalyPoint]
    total_points: int
    anomaly_count: int


class StructuralBreak(BaseModel):
    date: datetime.date
    index: int
    method: str
    confidence: float


class Regime(BaseModel):
    start_date: str
    end_date: str
    label: str  # "rising", "falling", "stable"
    mean_value: float
    mean_return: float
    volatility: float


class TrendAnalysis(BaseModel):
    source: str
    query: str
    series_length: int
    trend: TrendSignal
    seasonality: SeasonalityResult
    anomalies: AnomalyReport
    structural_breaks: list[StructuralBreak]
    regimes: list[Regime] = []


# --- Phase 4: Forecasting models ---


class ForecastPoint(BaseModel):
    date: datetime.date
    value: float
    lower_ci: float
    upper_ci: float


class ModelForecast(BaseModel):
    model_name: str
    points: list[ForecastPoint]


class ModelEvaluation(BaseModel):
    model_name: str
    mae: float
    rmse: float
    mape: float
    train_size: int
    test_size: int


class ForecastComparison(BaseModel):
    source: str
    query: str
    series_length: int
    horizon: int
    forecasts: list[ModelForecast]
    evaluations: list[ModelEvaluation]
    recommended_model: str


# --- Event Context models ---


class EventContext(BaseModel):
    """Context about real-world events near anomaly dates."""

    date: str
    headline: str
    source_url: str | None = None
    relevance: str | None = None


# --- Phase 5: AI Commentary models ---


class RiskFlag(BaseModel):
    label: str
    description: str


class InsightReport(BaseModel):
    source: str
    query: str
    summary: str
    risk_flags: list[RiskFlag]
    recommended_action: str | None
    prompt_version: str
    model_used: str


# --- Natural Language Query models ---


# --- Correlation models ---


class CorrelationCoefficient(BaseModel):
    r: float
    p_value: float


class LagCorrelation(BaseModel):
    lag: int
    correlation: float


class ScatterPoint(BaseModel):
    x: float
    y: float


class CorrelateItem(BaseModel):
    source: str
    query: str
    start: datetime.date | None = None
    end: datetime.date | None = None


class CorrelateRequest(BaseModel):
    series_a: CorrelateItem
    series_b: CorrelateItem
    start: datetime.date | None = None
    end: datetime.date | None = None
    resample: str | None = None
    refresh: bool = False


class CorrelateResponse(BaseModel):
    series_a_label: str
    series_b_label: str
    aligned_points: int
    pearson: CorrelationCoefficient
    spearman: CorrelationCoefficient
    lag_analysis: list[LagCorrelation]
    scatter: list[ScatterPoint]


# --- Comparison models ---


class CompareItem(BaseModel):
    source: str
    query: str
    start: datetime.date | None = None
    end: datetime.date | None = None


class CompareRequest(BaseModel):
    items: list[CompareItem] = Field(..., min_length=2, max_length=3)
    resample: str | None = None
    apply: str | None = None
    refresh: bool = False


class CompareResponse(BaseModel):
    series: list[TimeSeries]
    analyses: list["TrendAnalysis"] | None = None
    count: int


# --- Natural Language Query models ---


class NaturalQueryRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=500)


class NaturalQueryResponse(BaseModel):
    source: str
    query: str
    horizon: int = 14
    start: datetime.date | None = None
    end: datetime.date | None = None
    resample: str | None = None
    apply: str | None = None
    interpretation: str
    alert: bool = False


class NaturalAlertResponse(BaseModel):
    source: str
    query: str
    threshold_direction: str  # "above" or "below"
    threshold_value: float
    name: str
    interpretation: str
    alert: bool = True


class NaturalQueryError(BaseModel):
    error: str
    suggestions: list[str] = Field(default_factory=list)


class NaturalCompareItem(BaseModel):
    source: str
    query: str
    start: datetime.date | None = None
    end: datetime.date | None = None


class NaturalCompareResponse(BaseModel):
    items: list[NaturalCompareItem] = Field(..., min_length=2, max_length=3)
    resample: str | None = None
    interpretation: str


# --- Cohort comparison models ---


class CohortMember(BaseModel):
    source: str
    query: str
    total_return: float
    max_drawdown: float
    volatility: float
    rank: int
    normalized_points: list[DataPoint]


class CohortRequest(BaseModel):
    source: str
    queries: list[str] = Field(..., min_length=2, max_length=20)
    start_date: str | None = None
    end_date: str | None = None
    normalize: bool = True


class CohortResponse(BaseModel):
    source: str
    members: list[CohortMember]
    period_start: str | None
    period_end: str | None


# --- Saved Views models ---


class SaveViewRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source: str
    query: str
    horizon: int = 14
    start: datetime.date | None = None
    end: datetime.date | None = None
    resample: str | None = None
    apply: str | None = None
    anomaly_method: str = "zscore"


class SavedViewResponse(BaseModel):
    hash_id: str
    name: str
    source: str
    query: str
    horizon: int
    start: datetime.date | None = None
    end: datetime.date | None = None
    resample: str | None = None
    apply: str | None = None
    anomaly_method: str
    created_at: datetime.datetime


# --- Chat Follow-up models ---


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class DataContext(BaseModel):
    """Rich context about the data for follow-up questions."""

    # Basic info
    data_points_count: int
    date_range: str  # e.g., "2024-01-01 to 2024-12-31"

    # Statistics
    min_value: float
    max_value: float
    mean_value: float
    recent_values: list[dict]  # Last 5-10 data points [{date, value}, ...]

    # Trend analysis
    trend_direction: str  # rising, falling, stable
    trend_momentum: float

    # Anomalies
    anomaly_count: int
    anomalies: list[dict]  # [{date, value, zscore}, ...]

    # Structural breaks
    structural_breaks: list[dict]  # [{date, method}, ...]

    # Seasonality
    seasonality_detected: bool
    seasonality_period: int | None = None

    # Forecast (optional)
    forecast_horizon: int | None = None
    forecast_values: list[dict] | None = (
        None  # [{date, value, lower_ci, upper_ci}, ...]
    )


class InsightFollowupRequest(BaseModel):
    source: str
    query: str
    messages: list[ChatMessage]  # Conversation history
    context_summary: str  # The initial AI insight summary
    data_context: DataContext | None = None  # Rich data context


class CompareInsightFollowupRequest(BaseModel):
    items: list[CompareItem]
    messages: list[ChatMessage]  # Conversation history
    context_summary: str  # The initial AI comparison summary
    data_contexts: list[DataContext] | None = None  # Rich context for each series


# --- Causal Impact models ---


class CausalImpactPoint(BaseModel):
    date: datetime.date
    actual: float
    predicted: float
    lower_ci: float
    upper_ci: float
    impact: float


class CausalImpactResponse(BaseModel):
    source: str
    query: str
    event_date: str
    pre_period_length: int
    post_period_length: int
    cumulative_impact: float
    relative_impact_pct: float
    p_value: float
    significant: bool
    summary: str
    pointwise: list[CausalImpactPoint]


# --- Watchlist models ---


class WatchlistAddRequest(BaseModel):
    """Request to add a trend to the watchlist."""

    name: str  # User-friendly name for this watch
    source: str
    query: str
    resample: str | None = None
    threshold_direction: str | None = None  # "above" or "below"
    threshold_value: float | None = None


class WatchlistItemResponse(BaseModel):
    """Response for a single watchlist item."""

    id: int
    name: str
    source: str
    query: str
    resample: str | None = None
    threshold_direction: str | None = None
    threshold_value: float | None = None
    last_value: float | None = None
    last_checked_at: datetime.datetime | None = None
    created_at: datetime.datetime
    # Computed fields for status
    triggered: bool = False  # True if threshold crossed
    trend_direction: str | None = None  # "rising", "falling", "stable"


class WatchlistCheckResponse(BaseModel):
    """Response from checking/refreshing the watchlist."""

    items: list[WatchlistItemResponse]
    checked_at: datetime.datetime
    alerts: list[WatchlistItemResponse] = Field(default_factory=list)


# --- Notification models ---


class NotificationConfigRequest(BaseModel):
    """Request to save/update notification config."""

    webhook_url: str
    channel: str = "generic"
    enabled: bool = True


class NotificationConfigResponse(BaseModel):
    """Response for notification config."""

    webhook_url: str
    channel: str
    enabled: bool
    created_at: datetime.datetime


class NotificationStatusResponse(BaseModel):
    """Response for notification scheduler status."""

    running: bool
    last_check: str | None
    next_check: str | None
    interval: int
