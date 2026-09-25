"""Statistical forecasting: AutoETS wrapper via statsforecast."""

import datetime

import numpy as np

from app.forecasting.frequency import future_dates
from app.logging_config import get_logger
from app.models.schemas import ForecastPoint, ModelForecast

logger = get_logger(__name__)

MIN_SERIES_LENGTH = 7

# statsforecast's ETS doesn't support seasonal periods above this
MAX_SEASON_LENGTH = 24


def effective_season_length(season_length: int | None, n: int) -> int:
    """Seasonal period to use, or 1 (non-seasonal) when it can't be fit.

    ETS needs at least two full seasons of data.
    """
    if season_length is None or season_length < 2:
        return 1
    if season_length > MAX_SEASON_LENGTH or n < 2 * season_length:
        return 1
    return int(season_length)


def forecast_autoets(
    dates: list[datetime.date],
    values: np.ndarray,
    horizon: int,
    season_length: int | None = None,
) -> ModelForecast:
    """Forecast using AutoETS from statsforecast.

    ``season_length`` is the detected seasonal period in points; it falls back
    to non-seasonal when missing or when there are fewer than 2 seasons.

    Returns empty ModelForecast if series is too short, horizon <= 0,
    or if the model fails to converge.
    """
    if len(values) < MIN_SERIES_LENGTH or horizon <= 0:
        return ModelForecast(model_name="autoets", points=[])

    try:
        from statsforecast.models import AutoETS

        model = AutoETS(
            season_length=effective_season_length(season_length, len(values))
        )
        model.fit(y=values)
        prediction = model.predict(h=horizon, level=[95])

        points = []
        for step, date in enumerate(future_dates(dates, horizon)):
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
