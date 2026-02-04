"""Metrics (MAE/RMSE/MAPE) and train/test backtesting."""

import datetime
from collections.abc import Callable

import numpy as np

from app.models.schemas import ModelEvaluation, ModelForecast

MIN_TRAIN_SIZE = 10


def compute_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    """Compute MAE, RMSE, and MAPE between actual and predicted arrays."""
    errors = actual - predicted
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors**2)))

    # MAPE: skip entries where actual is zero
    nonzero_mask = actual != 0
    if np.any(nonzero_mask):
        mape = float(np.mean(np.abs(errors[nonzero_mask] / actual[nonzero_mask])) * 100)
    else:
        mape = 0.0

    return {"mae": mae, "rmse": rmse, "mape": mape}


def backtest(
    dates: list[datetime.date],
    values: np.ndarray,
    forecast_fn: Callable[[list[datetime.date], np.ndarray, int], ModelForecast],
    model_name: str,
    test_size: int | None = None,
) -> ModelEvaluation | None:
    """Split data into train/test, forecast on test, and evaluate.

    Returns None if the training split would be smaller than MIN_TRAIN_SIZE.
    """
    n = len(values)
    if test_size is None:
        test_size = max(1, int(n * 0.2))

    train_size = n - test_size
    if train_size < MIN_TRAIN_SIZE:
        return None

    train_dates = dates[:train_size]
    train_values = values[:train_size]

    forecast = forecast_fn(train_dates, train_values, test_size)

    if len(forecast.points) == 0:
        return None

    predicted = np.array([p.value for p in forecast.points], dtype=np.float64)
    actual = values[train_size : train_size + len(predicted)]

    # Align lengths in case forecast returned fewer points
    min_len = min(len(actual), len(predicted))
    if min_len == 0:
        return None

    actual = actual[:min_len]
    predicted = predicted[:min_len]

    metrics = compute_metrics(actual, predicted)

    return ModelEvaluation(
        model_name=model_name,
        mae=metrics["mae"],
        rmse=metrics["rmse"],
        mape=metrics["mape"],
        train_size=train_size,
        test_size=min_len,
    )
