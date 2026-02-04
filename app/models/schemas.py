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


class DataSourceInfo(BaseModel):
    name: str
    description: str


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
