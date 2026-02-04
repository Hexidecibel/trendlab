import datetime

from sqlalchemy import (
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
