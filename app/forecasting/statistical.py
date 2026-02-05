"""Statistical forecasting: AutoETS wrapper via statsforecast."""

import datetime

import numpy as np

from app.logging_config import get_logger
from app.models.schemas import ForecastPoint, ModelForecast

logger = get_logger(__name__)

MIN_SERIES_LENGTH = 7


def forecast_autoets(
    dates: list[datetime.date],
    values: np.ndarray,
    horizon: int,
    season_length: int = 7,
) -> ModelForecast:
    """Forecast using AutoETS from statsforecast.

    Returns empty ModelForecast if series is too short, horizon <= 0,
    or if the model fails to converge.
    """
    if len(values) < MIN_SERIES_LENGTH or horizon <= 0:
        return ModelForecast(model_name="autoets", points=[])

    try:
        from statsforecast.models import AutoETS

        model = AutoETS(season_length=season_length)
        model.fit(y=values)
        prediction = model.predict(h=horizon, level=[95])

        last_date = dates[-1]
        points = []
        for step in range(horizon):
            date = last_date + datetime.timedelta(days=step + 1)
            value = float(prediction["mean"][step])
            lower = float(prediction["lo-95"][step])
            upper = float(prediction["hi-95"][step])
            points.append(
                ForecastPoint(
                    date=date,
                    value=value,
                    lower_ci=lower,
                    upper_ci=upper,
                )
            )

        return ModelForecast(model_name="autoets", points=points)

    except Exception:
        logger.warning("AutoETS failed, returning empty forecast", exc_info=True)
        return ModelForecast(model_name="autoets", points=[])
