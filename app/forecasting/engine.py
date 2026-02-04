"""Forecast orchestrator: run all models, evaluate, recommend best."""

import logging

import numpy as np

from app.forecasting.baseline import (
    forecast_linear,
    forecast_moving_average,
    forecast_naive,
)
from app.forecasting.evaluation import backtest
from app.forecasting.statistical import forecast_autoets
from app.models.schemas import (
    ForecastComparison,
    ModelEvaluation,
    ModelForecast,
    TimeSeries,
)

logger = logging.getLogger(__name__)


def forecast(ts: TimeSeries, horizon: int = 14) -> ForecastComparison:
    """Run all forecast models, backtest each, and recommend the best."""
    if len(ts.points) == 0:
        raise ValueError("Cannot forecast empty series")

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
        try:
            model_forecast = fn(dates, values, horizon, **kwargs)
        except Exception:
            logger.warning("Model %s failed during forecast", model_name, exc_info=True)
            continue

        if len(model_forecast.points) == 0:
            continue

        forecasts.append(model_forecast)

        try:
            evaluation = backtest(dates, values, fn, model_name)
        except Exception:
            logger.warning("Model %s failed during backtest", model_name, exc_info=True)
            continue

        if evaluation is not None:
            evaluations.append(evaluation)

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

    return ForecastComparison(
        source=ts.source,
        query=ts.query,
        series_length=len(ts.points),
        horizon=horizon,
        forecasts=forecasts,
        evaluations=evaluations,
        recommended_model=recommended,
    )
