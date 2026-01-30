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
