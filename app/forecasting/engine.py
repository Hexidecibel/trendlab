"""Forecast orchestrator: run all models, evaluate, recommend best."""

import time

import numpy as np

from app.forecasting.baseline import (
    forecast_linear,
    forecast_moving_average,
    forecast_naive,
)
from app.forecasting.evaluation import backtest
from app.forecasting.statistical import forecast_autoets
from app.logging_config import get_logger
from app.models.schemas import (
    ForecastComparison,
    ModelEvaluation,
    ModelForecast,
    TimeSeries,
)

logger = get_logger(__name__)


def forecast(ts: TimeSeries, horizon: int = 14) -> ForecastComparison:
    """Run all forecast models, backtest each, and recommend the best."""
    if len(ts.points) == 0:
        raise ValueError("Cannot forecast empty series")

    log = logger.with_fields(
        source=ts.source, query=ts.query, series_length=len(ts.points), horizon=horizon
    )
    log.info("Starting forecast")
    total_start = time.perf_counter()

    dates = [p.date for p in ts.points]
    values = np.array([p.value for p in ts.points], dtype=np.float64)

    # Run all models
    model_fns: list[tuple[str, callable, dict]] = [
        ("naive", forecast_naive, {}),
        ("moving_average", forecast_moving_average, {}),
        ("linear", forecast_linear, {}),
        ("autoets", forecast_autoets, {}),
    ]

    forecasts: list[ModelForecast] = []
    evaluations: list[ModelEvaluation] = []

    for model_name, fn, kwargs in model_fns:
        model_start = time.perf_counter()
        try:
            model_forecast = fn(dates, values, horizon, **kwargs)
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
