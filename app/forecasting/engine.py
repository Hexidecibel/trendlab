"""Forecast orchestrator: run all models, evaluate, recommend best."""

import functools
import time

import numpy as np

from app.analysis.seasonality import analyze_seasonality
from app.forecasting.baseline import (
    forecast_linear,
    forecast_moving_average,
    forecast_naive,
)
from app.forecasting.evaluation import backtest
from app.forecasting.frequency import cap_horizon, infer_step
from app.forecasting.statistical import forecast_autoets
from app.logging_config import get_logger
from app.models.schemas import (
    ForecastComparison,
    ModelEvaluation,
    ModelForecast,
    TimeSeries,
)

logger = get_logger(__name__)


def forecast(
    ts: TimeSeries,
    horizon: int = 14,
    seasonal_period: int | None = None,
) -> ForecastComparison:
    """Run all forecast models, backtest each, and recommend the best.

    ``horizon`` is a number of periods at the series' own step (days for
    daily data, months for monthly data, ...), capped at half the series
    length. ``seasonal_period`` (in points) feeds AutoETS; it is detected
    from the series when not given.
    """
    if len(ts.points) == 0:
        raise ValueError("Cannot forecast empty series")

    horizon = cap_horizon(horizon, len(ts.points))
    if seasonal_period is None:
        seasonality = analyze_seasonality(ts)
        seasonal_period = seasonality.period_days if seasonality.detected else None

    log = logger.with_fields(
        source=ts.source, query=ts.query, series_length=len(ts.points), horizon=horizon
    )
    log.with_fields(
        step=infer_step([p.date for p in ts.points]).label,
        seasonal_period=seasonal_period,
    ).info("Starting forecast")
    total_start = time.perf_counter()

    dates = [p.date for p in ts.points]
    values = np.array([p.value for p in ts.points], dtype=np.float64)

    # Run all models
    model_fns: list[tuple[str, callable, dict]] = [
        ("naive", forecast_naive, {}),
        ("moving_average", forecast_moving_average, {}),
        ("linear", forecast_linear, {}),
        ("autoets", forecast_autoets, {"season_length": seasonal_period}),
    ]

    forecasts: list[ModelForecast] = []
    evaluations: list[ModelEvaluation] = []

    for model_name, base_fn, kwargs in model_fns:
        fn = functools.partial(base_fn, **kwargs) if kwargs else base_fn
        model_start = time.perf_counter()
        try:
            model_forecast = fn(dates, values, horizon)
        except Exception:
            log.with_fields(model=model_name).warning(
                "Model failed during forecast", exc_info=True
            )
            continue

        if len(model_forecast.points) == 0:
            continue

        forecasts.append(model_forecast)

        try:
            evaluation = backtest(dates, values, fn, model_name)
        except Exception:
            log.with_fields(model=model_name).warning(
                "Model failed during backtest", exc_info=True
            )
            continue

        model_ms = (time.perf_counter() - model_start) * 1000
        if evaluation is not None:
            evaluations.append(evaluation)
            log.with_fields(
                model=model_name,
                mae=round(evaluation.mae, 4),
                elapsed_ms=round(model_ms, 2),
            ).debug("Model completed")

    # Recommend model with lowest MAE
    if evaluations:
        best = min(evaluations, key=lambda e: e.mae)
        recommended = best.model_name
    elif forecasts:
        # No evaluations succeeded, fall back to naive if present
        forecast_names = {f.model_name for f in forecasts}
        recommended = "naive" if "naive" in forecast_names else forecasts[0].model_name
    else:
        recommended = "naive"

    total_ms = (time.perf_counter() - total_start) * 1000
    log.with_fields(
        recommended_model=recommended,
        models_run=len(forecasts),
        elapsed_ms=round(total_ms, 2),
    ).info("Forecast complete")

    return ForecastComparison(
        source=ts.source,
        query=ts.query,
        series_length=len(ts.points),
        horizon=horizon,
        forecasts=forecasts,
        evaluations=evaluations,
        recommended_model=recommended,
    )
