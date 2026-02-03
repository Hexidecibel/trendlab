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
