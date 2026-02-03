"""Anomaly detection using z-score and IQR methods."""

import datetime

import numpy as np

from app.models.schemas import AnomalyPoint, AnomalyReport, TimeSeries


def detect_zscore(
    dates: list[datetime.date],
    values: np.ndarray,
    threshold: float = 2.5,
) -> AnomalyReport:
    """Flag points where |z-score| exceeds threshold."""
    std = float(np.std(values))
    if std == 0:
        return AnomalyReport(
            method="zscore",
            threshold=threshold,
            anomalies=[],
            total_points=len(values),
            anomaly_count=0,
        )

    mean = float(np.mean(values))
    z_scores = (values - mean) / std

    anomalies = []
    for i, z in enumerate(z_scores):
        if abs(z) > threshold:
            anomalies.append(
                AnomalyPoint(
                    date=dates[i],
                    value=float(values[i]),
                    score=float(abs(z)),
                    method="zscore",
                )
            )

    return AnomalyReport(
        method="zscore",
        threshold=threshold,
        anomalies=anomalies,
        total_points=len(values),
        anomaly_count=len(anomalies),
    )


def detect_iqr(
    dates: list[datetime.date],
    values: np.ndarray,
    k: float = 1.5,
) -> AnomalyReport:
    """Flag points outside [Q1 - k*IQR, Q3 + k*IQR]."""
    q1 = float(np.percentile(values, 25))
    q3 = float(np.percentile(values, 75))
    iqr = q3 - q1

    if iqr == 0:
        # All values in the IQR are identical — any value != median is anomalous
        median = float(np.median(values))
        anomalies = []
        for i, v in enumerate(values):
            if v != median:
                anomalies.append(
                    AnomalyPoint(
                        date=dates[i],
                        value=float(v),
                        score=float(abs(v - median)),
                        method="iqr",
                    )
                )
        return AnomalyReport(
            method="iqr",
            threshold=k,
            anomalies=anomalies,
            total_points=len(values),
            anomaly_count=len(anomalies),
        )

    lower = q1 - k * iqr
    upper = q3 + k * iqr

    anomalies = []
    for i, v in enumerate(values):
        if v < lower or v > upper:
            # Score = distance from nearest bound, normalized by IQR
            distance = max(lower - v, v - upper)
            score = float(distance / iqr)
            anomalies.append(
                AnomalyPoint(
                    date=dates[i],
                    value=float(v),
                    score=score,
                    method="iqr",
                )
            )

    return AnomalyReport(
        method="iqr",
        threshold=k,
        anomalies=anomalies,
        total_points=len(values),
        anomaly_count=len(anomalies),
    )


def analyze_anomalies(
    ts: TimeSeries,
    method: str = "zscore",
    **kwargs: float,
) -> AnomalyReport:
    """Run anomaly detection on a TimeSeries."""
    if len(ts.points) == 0:
        return AnomalyReport(
            method=method,
            threshold=kwargs.get("threshold", kwargs.get("k", 2.5)),
            anomalies=[],
            total_points=0,
            anomaly_count=0,
        )

    dates = [p.date for p in ts.points]
    values = np.array([p.value for p in ts.points], dtype=np.float64)

    if method == "zscore":
        return detect_zscore(dates, values, **kwargs)
    elif method == "iqr":
        return detect_iqr(dates, values, **kwargs)
    else:
        raise ValueError(f"Unknown anomaly detection method: '{method}'")
