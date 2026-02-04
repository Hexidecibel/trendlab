"""Baseline forecasting models: naive, moving average, linear regression."""

import datetime

import numpy as np

from app.models.schemas import ForecastPoint, ModelForecast

Z_SCORE_95 = 1.96


def _make_forecast_points(
    last_date: datetime.date,
    forecast_values: np.ndarray,
    residual_std: float,
    horizon: int,
) -> list[ForecastPoint]:
    """Build ForecastPoint list with widening 95% confidence intervals."""
    points = []
    for step in range(1, horizon + 1):
        date = last_date + datetime.timedelta(days=step)
        value = float(forecast_values[step - 1])
        width = Z_SCORE_95 * residual_std * np.sqrt(step)
        points.append(
            ForecastPoint(
                date=date,
                value=value,
                lower_ci=value - width,
                upper_ci=value + width,
            )
        )
    return points


def forecast_naive(
    dates: list[datetime.date],
    values: np.ndarray,
    horizon: int,
) -> ModelForecast:
    """Repeat last observed value. CI from std of first differences."""
    if len(values) == 0 or horizon <= 0:
        return ModelForecast(model_name="naive", points=[])

    last_value = float(values[-1])
    forecast_values = np.full(horizon, last_value)

    if len(values) >= 2:
        residual_std = float(np.std(np.diff(values), ddof=1))
    else:
        residual_std = 0.0

    return ModelForecast(
        model_name="naive",
        points=_make_forecast_points(dates[-1], forecast_values, residual_std, horizon),
    )


def forecast_moving_average(
    dates: list[datetime.date],
    values: np.ndarray,
    horizon: int,
    window: int = 7,
) -> ModelForecast:
    """Project trailing MA flat. Falls back to all values if len < window."""
    if len(values) == 0 or horizon <= 0:
        return ModelForecast(model_name="moving_average", points=[])

    effective_window = min(window, len(values))
    ma_value = float(np.mean(values[-effective_window:]))
    forecast_values = np.full(horizon, ma_value)

    if len(values) >= 2:
        residual_std = float(np.std(np.diff(values), ddof=1))
    else:
        residual_std = 0.0

    return ModelForecast(
        model_name="moving_average",
        points=_make_forecast_points(dates[-1], forecast_values, residual_std, horizon),
    )


def forecast_linear(
    dates: list[datetime.date],
    values: np.ndarray,
    horizon: int,
) -> ModelForecast:
    """Linear regression extrapolation. CI from residual std."""
    if len(values) == 0 or horizon <= 0:
        return ModelForecast(model_name="linear", points=[])

    n = len(values)
    t = np.arange(n, dtype=np.float64)

    if n < 2:
        # Single point: flat forecast, zero CI
        forecast_values = np.full(horizon, float(values[0]))
        residual_std = 0.0
    else:
        coeffs = np.polyfit(t, values, 1)
        slope, intercept = coeffs[0], coeffs[1]

        fitted = np.polyval(coeffs, t)
        residuals = values - fitted
        residual_std = float(np.std(residuals, ddof=1)) if n > 2 else 0.0

        future_t = np.arange(n, n + horizon, dtype=np.float64)
        forecast_values = slope * future_t + intercept

    return ModelForecast(
        model_name="linear",
        points=_make_forecast_points(dates[-1], forecast_values, residual_std, horizon),
    )
