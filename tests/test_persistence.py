import datetime

import pytest
from sqlalchemy import inspect

import app.db.engine as db_engine
from app.db.repository import (
    get_analysis,
    get_forecast,
    get_query_config,
    get_series,
    save_analysis,
    save_forecast,
    save_query_config,
    save_series,
)
from app.models.schemas import (
    AnomalyReport,
    DataPoint,
    ForecastComparison,
    ForecastPoint,
    ModelEvaluation,
    ModelForecast,
    MovingAverage,
    SeasonalityResult,
    TimeSeries,
    TrendAnalysis,
    TrendSignal,
)


@pytest.fixture
async def db():
    """Initialize a fresh in-memory database for each test."""
    await db_engine.init_db("sqlite+aiosqlite://")
    yield
    # Engine is disposed after each test via init_db overwrite


def _make_series() -> TimeSeries:
    return TimeSeries(
        source="pypi",
        query="fastapi",
        points=[
            DataPoint(date=datetime.date(2025, 1, 1), value=100.0),
            DataPoint(date=datetime.date(2025, 1, 2), value=110.0),
            DataPoint(date=datetime.date(2025, 1, 3), value=105.0),
        ],
        metadata={"unit": "downloads"},
    )


def _make_analysis() -> TrendAnalysis:
    return TrendAnalysis(
        source="pypi",
        query="fastapi",
        series_length=3,
        trend=TrendSignal(
            direction="rising",
            momentum=0.5,
            acceleration=0.1,
            moving_averages=[
                MovingAverage(
                    window=7,
                    values=[DataPoint(date=datetime.date(2025, 1, 1), value=100.0)],
                )
            ],
            momentum_series=[DataPoint(date=datetime.date(2025, 1, 1), value=0.5)],
        ),
        seasonality=SeasonalityResult(
            detected=False, period_days=None, strength=None, autocorrelation=[0.1]
        ),
        anomalies=AnomalyReport(
            method="zscore",
            threshold=2.0,
            anomalies=[],
            total_points=3,
            anomaly_count=0,
        ),
        structural_breaks=[],
    )


def _make_forecast() -> ForecastComparison:
    return ForecastComparison(
        source="pypi",
        query="fastapi",
        series_length=3,
        horizon=7,
        forecasts=[
            ModelForecast(
                model_name="naive",
                points=[
                    ForecastPoint(
                        date=datetime.date(2025, 1, 4),
                        value=105.0,
                        lower_ci=95.0,
                        upper_ci=115.0,
                    )
                ],
            )
        ],
        evaluations=[
            ModelEvaluation(
                model_name="naive",
                mae=5.0,
                rmse=6.0,
                mape=0.05,
                train_size=2,
                test_size=1,
            )
        ],
        recommended_model="naive",
    )


class TestDbInit:
    async def test_tables_created(self, db):
        """init_db creates all expected tables."""
        async with db_engine.async_session() as session:
            conn = await session.connection()
            table_names = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
        assert "series_records" in table_names
        assert "analysis_records" in table_names
        assert "forecast_records" in table_names
        assert "query_configs" in table_names


class TestSeriesRoundTrip:
    async def test_save_and_retrieve(self, db):
        """Save a TimeSeries and retrieve it by source/query."""
        ts = _make_series()
        record = await save_series(ts)
        assert record.id is not None

        retrieved = await get_series("pypi", "fastapi")
        assert retrieved is not None
        assert retrieved.source == "pypi"
        assert retrieved.query == "fastapi"
        assert len(retrieved.points) == 3
        assert retrieved.points[0].date == datetime.date(2025, 1, 1)
        assert retrieved.points[0].value == 100.0
        assert retrieved.metadata["unit"] == "downloads"

    async def test_retrieve_missing_returns_none(self, db):
        """get_series returns None for nonexistent series."""
        result = await get_series("pypi", "nonexistent")
        assert result is None

    async def test_save_updates_existing(self, db):
        """Saving same source/query overwrites the previous record."""
        ts1 = _make_series()
        await save_series(ts1)

        ts2 = TimeSeries(
            source="pypi",
            query="fastapi",
            points=[DataPoint(date=datetime.date(2025, 2, 1), value=200.0)],
        )
        await save_series(ts2)

        retrieved = await get_series("pypi", "fastapi")
        assert len(retrieved.points) == 1
        assert retrieved.points[0].value == 200.0

    async def test_date_range_filtering(self, db):
        """Series with different date ranges are stored separately."""
        ts = _make_series()
        await save_series(
            ts,
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 1, 31),
        )
        await save_series(
            ts,
            start_date=datetime.date(2025, 2, 1),
            end_date=datetime.date(2025, 2, 28),
        )

        jan = await get_series(
            "pypi",
            "fastapi",
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 1, 31),
        )
        feb = await get_series(
            "pypi",
            "fastapi",
            start_date=datetime.date(2025, 2, 1),
            end_date=datetime.date(2025, 2, 28),
        )
        assert jan is not None
        assert feb is not None


class TestAnalysisRoundTrip:
    async def test_save_and_retrieve(self, db):
        """Save analysis result linked to a series and retrieve it."""
        ts = _make_series()
        series_record = await save_series(ts)

        analysis = _make_analysis()
        await save_analysis(series_record.id, analysis)

        retrieved = await get_analysis(series_record.id)
        assert retrieved is not None
        assert retrieved.source == "pypi"
        assert retrieved.trend.direction == "rising"
        assert retrieved.series_length == 3

    async def test_retrieve_missing_returns_none(self, db):
        """get_analysis returns None when no analysis exists."""
        result = await get_analysis(999)
        assert result is None


class TestForecastRoundTrip:
    async def test_save_and_retrieve(self, db):
        """Save forecast result linked to a series and retrieve it."""
        ts = _make_series()
        series_record = await save_series(ts)

        fc = _make_forecast()
        await save_forecast(series_record.id, fc)

        retrieved = await get_forecast(series_record.id, horizon=7)
        assert retrieved is not None
        assert retrieved.source == "pypi"
        assert retrieved.horizon == 7
        assert retrieved.recommended_model == "naive"
        assert len(retrieved.forecasts) == 1

    async def test_retrieve_wrong_horizon_returns_none(self, db):
        """get_forecast returns None for non-matching horizon."""
        ts = _make_series()
        series_record = await save_series(ts)
        fc = _make_forecast()
        await save_forecast(series_record.id, fc)

        result = await get_forecast(series_record.id, horizon=30)
        assert result is None


class TestQueryConfig:
    async def test_save_and_retrieve(self, db):
        """Save and retrieve a query config."""
        config_id = await save_query_config(
            source="pypi",
            query="fastapi",
            horizon=14,
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 3, 1),
            params={"resample": "week"},
        )
        assert config_id is not None

        retrieved = await get_query_config(config_id)
        assert retrieved is not None
        assert retrieved["source"] == "pypi"
        assert retrieved["query"] == "fastapi"
        assert retrieved["horizon"] == 14
        assert retrieved["params"]["resample"] == "week"
