import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


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


class DataSourceInfo(BaseModel):
    name: str
    description: str
    form_fields: list[FormField] = Field(default_factory=list)


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


class TrendAnalysis(BaseModel):
    source: str
    query: str
    series_length: int
    trend: TrendSignal
    seasonality: SeasonalityResult
    anomalies: AnomalyReport
    structural_breaks: list[StructuralBreak]


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
    interpretation: str


class NaturalQueryError(BaseModel):
    error: str
    suggestions: list[str] = Field(default_factory=list)
