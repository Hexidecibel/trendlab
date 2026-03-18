import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow():
    return datetime.datetime.now(datetime.UTC)


class Base(DeclarativeBase):
    pass


class SeriesRecord(Base):
    __tablename__ = "series_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    query = Column(String, nullable=False)
    points_json = Column(Text, nullable=False)
    metadata_json = Column(Text)
    fetched_at = Column(DateTime, nullable=False, default=_utcnow)
    start_date = Column(Date)
    end_date = Column(Date)

    analyses = relationship(
        "AnalysisRecord", back_populates="series", cascade="all, delete-orphan"
    )
    forecasts = relationship(
        "ForecastRecord", back_populates="series", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("source", "query", "start_date", "end_date", name="uq_series"),
    )


class AnalysisRecord(Base):
    __tablename__ = "analysis_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_id = Column(Integer, ForeignKey("series_records.id"), nullable=False)
    result_json = Column(Text, nullable=False)
    anomaly_method = Column(String)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    series = relationship("SeriesRecord", back_populates="analyses")


class ForecastRecord(Base):
    __tablename__ = "forecast_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_id = Column(Integer, ForeignKey("series_records.id"), nullable=False)
    result_json = Column(Text, nullable=False)
    horizon = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    series = relationship("SeriesRecord", back_populates="forecasts")


class QueryConfig(Base):
    __tablename__ = "query_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    query = Column(String, nullable=False)
    horizon = Column(Integer)
    start_date = Column(Date)
    end_date = Column(Date)
    params_json = Column(Text)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class SavedView(Base):
    __tablename__ = "saved_views"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hash_id = Column(String(12), unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    source = Column(String, nullable=False)
    query = Column(String, nullable=False)
    horizon = Column(Integer, default=14)
    start_date = Column(Date)
    end_date = Column(Date)
    resample = Column(String)
    apply = Column(String)
    anomaly_method = Column(String, default="zscore")
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class ForecastSnapshot(Base):
    __tablename__ = "forecast_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    query = Column(String, nullable=False)
    forecast_date = Column(Date, nullable=False)  # Date when forecast was made
    horizon = Column(Integer, nullable=False)
    model_name = Column(String, nullable=False)
    # [{date, value, lower_ci, upper_ci}, ...]
    predictions_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  # User-friendly name
    source = Column(String, nullable=False)
    query = Column(String, nullable=False)
    resample = Column(String)  # Optional resampling
    threshold_direction = Column(String)  # 'above', 'below', or None
    threshold_value = Column(Integer)  # Threshold for alerts
    last_value = Column(Integer)  # Most recent value
    last_checked_at = Column(DateTime)  # When last refreshed
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("source", "query", name="uq_watchlist_source_query"),
    )


class NotificationConfig(Base):
    __tablename__ = "notification_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    webhook_url = Column(String, nullable=False)
    channel = Column(String, default="generic")  # slack, discord, generic
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
