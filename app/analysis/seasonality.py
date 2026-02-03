"""Seasonality detection via FFT-based autocorrelation."""

import numpy as np

from app.models.schemas import SeasonalityResult, TimeSeries

# Minimum autocorrelation peak to declare seasonality detected
STRENGTH_THRESHOLD = 0.3

# Need at least this many data points for meaningful analysis
MIN_POINTS = 14


def compute_autocorrelation(
    values: np.ndarray, max_lag: int | None = None
) -> np.ndarray:
    """FFT-based autocorrelation, normalized so lag-0 = 1.0.

    Uses the Wiener-Khinchin theorem: autocorrelation = IFFT(|FFT(x)|^2).
    Zero-pads to 2*n to avoid circular correlation artifacts.
    """
    centered = values - np.mean(values)
    n = len(centered)

    # FFT with zero-padding
    fft = np.fft.rfft(centered, n=2 * n)
    power = fft * np.conj(fft)
    acf = np.fft.irfft(power)[:n].real

    # Normalize by variance (acf[0]) so lag-0 = 1.0
    if acf[0] != 0:
        acf = acf / acf[0]

    if max_lag is not None:
        acf = acf[: max_lag + 1]

    return acf


def find_dominant_period(
    acf: np.ndarray, min_period: int = 2
) -> tuple[int | None, float | None]:
    """Find the dominant period from local peaks in the autocorrelation.

    A local peak is where acf[i] > acf[i-1] and acf[i] > acf[i+1].
    We look for the strongest local peak at lag >= min_period.
    """
    if len(acf) <= min_period + 1:
        return None, None

    best_lag = None
    best_value = -1.0

    for i in range(min_period, len(acf) - 1):
        if acf[i] > acf[i - 1] and acf[i] > acf[i + 1]:
            if acf[i] > best_value:
                best_value = float(acf[i])
                best_lag = i

    if best_lag is not None and best_value > STRENGTH_THRESHOLD:
        return best_lag, best_value

    return None, None


def analyze_seasonality(ts: TimeSeries) -> SeasonalityResult:
    """Detect periodic patterns in a TimeSeries."""
    values = np.array([p.value for p in ts.points], dtype=np.float64)

    if len(values) < MIN_POINTS:
        return SeasonalityResult(
            detected=False,
            period_days=None,
            strength=None,
            autocorrelation=[],
        )

    # Constant series has zero variance — no seasonality possible
    if np.std(values) == 0:
        return SeasonalityResult(
            detected=False,
            period_days=None,
            strength=None,
            autocorrelation=[1.0] + [0.0] * (len(values) // 2 - 1),
        )

    max_lag = len(values) // 2
    acf = compute_autocorrelation(values, max_lag=max_lag)
    period, strength = find_dominant_period(acf)

    return SeasonalityResult(
        detected=period is not None,
        period_days=period,
        strength=strength,
        autocorrelation=[float(v) for v in acf],
    )
