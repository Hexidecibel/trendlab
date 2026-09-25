import datetime
import math

import numpy as np
from scipy.stats import ttest_1samp

from app.models.schemas import CausalImpactPoint, CausalImpactResponse, TimeSeries


async def analyze_causal_impact(
    series: TimeSeries, event_date: str
) -> CausalImpactResponse:
    """Estimate the causal impact of an event on a time series.

    Splits the series at *event_date* into pre- and post-periods, fits a
    polynomial trend on the pre-period to build a counterfactual, then
    measures how far the post-period deviates from that counterfactual.
    """
    ev_date = datetime.date.fromisoformat(event_date)

    dates = [p.date for p in series.points]
    if not dates:
        raise ValueError("Series has no data points")

    if ev_date < dates[0] or ev_date > dates[-1]:
        raise ValueError(
            f"event_date {event_date} is outside series range "
            f"({dates[0].isoformat()} to {dates[-1].isoformat()})"
        )

    pre_points = [p for p in series.points if p.date < ev_date]
    post_points = [p for p in series.points if p.date >= ev_date]

    if len(pre_points) < 30:
        raise ValueError(
            f"Pre-period must have >= 30 data points, got {len(pre_points)}"
        )

    if len(post_points) == 0:
        raise ValueError("Post-period has no data points")

    # Numeric x-axis: days since first date
    origin = pre_points[0].date
    pre_x = np.array([(p.date - origin).days for p in pre_points], dtype=float)
    pre_y = np.array([p.value for p in pre_points], dtype=float)

    # Linear trend by default. A quadratic only when it fits the pre-period
    # clearly better (AIC) and isn't extrapolated further than the data it
    # was fitted on -- a curve projected far ahead quickly runs off (e.g. a
    # counterfactual below zero for page views), which makes the "impact"
    # meaningless.
    poly = np.poly1d(np.polyfit(pre_x, pre_y, 1))
    post_span = float((post_points[-1].date - origin).days) - float(pre_x[-1])
    pre_span = float(pre_x[-1] - pre_x[0])
    if len(pre_points) >= 3 and post_span <= pre_span:
        quad = np.poly1d(np.polyfit(pre_x, pre_y, 2))
        n = len(pre_points)

        def aic(f: np.poly1d, k: int) -> float:
            rss = float(np.sum((pre_y - f(pre_x)) ** 2))
            return n * math.log(max(rss / n, 1e-300)) + 2 * k

        if aic(quad, 3) < aic(poly, 2) - 2.0:
            poly = quad
    # Counts, prices, views... can't go below zero
    floor_zero = bool(np.all(pre_y >= 0))

    # Residual standard deviation for confidence intervals
    pre_residuals = pre_y - poly(pre_x)
    residual_std = (
        float(np.std(pre_residuals, ddof=1)) if len(pre_residuals) > 1 else 0.0
    )

    # Generate counterfactual for post-period
    pointwise: list[CausalImpactPoint] = []
    impacts: list[float] = []
    predicted_sum = 0.0

    for p in post_points:
        x = float((p.date - origin).days)
        predicted = float(poly(x))
        if floor_zero:
            predicted = max(predicted, 0.0)
        # Widen CI with distance from training data
        dist_factor = 1.0 + 0.01 * max(0, x - float(pre_x[-1]))
        ci_half = 1.96 * residual_std * dist_factor
        impact = p.value - predicted
        impacts.append(impact)
        predicted_sum += predicted

        pointwise.append(
            CausalImpactPoint(
                date=p.date,
                actual=p.value,
                predicted=round(predicted, 6),
                lower_ci=round(predicted - ci_half, 6),
                upper_ci=round(predicted + ci_half, 6),
                impact=round(impact, 6),
            )
        )

    cumulative_impact = sum(impacts)

    if abs(predicted_sum) > 1e-12:
        relative_impact_pct = (cumulative_impact / predicted_sum) * 100
    else:
        relative_impact_pct = 0.0

    # Statistical significance via one-sample t-test (H0: mean impact = 0)
    impacts_arr = np.array(impacts)
    mean_impact = float(np.mean(impacts_arr))
    std_impact = float(np.std(impacts_arr, ddof=1)) if len(impacts) > 1 else 0.0

    if len(impacts) < 2:
        p_value = 1.0
    elif std_impact < 1e-12:
        # Zero variance: if mean is also ~0, no effect; otherwise perfectly
        # consistent effect → p effectively 0.
        p_value = 1.0 if abs(mean_impact) < 1e-12 else 0.0
    else:
        _, p_value = ttest_1samp(impacts_arr, 0.0)
        if math.isnan(p_value):
            p_value = 1.0

    significant = p_value < 0.05

    # Build summary text
    direction = "positive" if cumulative_impact > 0 else "negative"
    sig_text = (
        "statistically significant" if significant else "not statistically significant"
    )
    summary = (
        f"The event on {event_date} had a {direction} impact. "
        f"Cumulative impact: {cumulative_impact:+.2f} ({relative_impact_pct:+.1f}%). "
        f"This effect is {sig_text} (p={p_value:.4f})."
    )

    return CausalImpactResponse(
        source=series.source,
        query=series.query,
        event_date=event_date,
        pre_period_length=len(pre_points),
        post_period_length=len(post_points),
        cumulative_impact=round(cumulative_impact, 6),
        relative_impact_pct=round(relative_impact_pct, 4),
        p_value=round(p_value, 6),
        significant=significant,
        summary=summary,
        pointwise=pointwise,
    )
