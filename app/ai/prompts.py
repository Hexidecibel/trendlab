"""Prompt templates, context formatter, and version registry for AI commentary."""

from app.models.schemas import ForecastComparison, TrendAnalysis

SYSTEM_PROMPT = (
    "You are a concise data analyst who explains trends to non-technical users. "
    "Avoid jargon. Be direct and specific about what the data shows. "
    "Include caveats where the data is uncertain or limited. "
    "When discussing forecasts, mention which model was used and its error rate. "
    "Keep responses focused and actionable."
)

PROMPT_REGISTRY: dict[str, str] = {
    "default": (
        "Analyze the following time-series data and provide a balanced summary "
        "covering the trend direction, any seasonal patterns, anomalies, "
        "structural changes, and the forecast outlook.\n\n{context}"
    ),
    "concise": (
        "Provide a 2-3 sentence executive summary of this time-series data. "
        "Focus on the most important finding and the forecast direction.\n\n"
        "{context}"
    ),
    "detailed": (
        "Provide a thorough analysis of this time-series data with the following "
        "sections:\n"
        "## Trend Overview\n"
        "## Seasonal Patterns\n"
        "## Anomalies & Structural Changes\n"
        "## Forecast Outlook\n"
        "## Risk Factors\n\n"
        "{context}"
    ),
}


def format_analysis_context(
    analysis: TrendAnalysis, forecast: ForecastComparison
) -> str:
    """Serialize structured analysis and forecast data into LLM-ready text."""
    lines = []

    # Series metadata
    lines.append(f"Source: {analysis.source}")
    lines.append(f"Query: {analysis.query}")
    lines.append(f"Series length: {analysis.series_length} data points")
    lines.append("")

    # Trend
    lines.append(f"Trend direction: {analysis.trend.direction}")
    lines.append(f"Momentum: {analysis.trend.momentum:.4f}")
    lines.append(f"Acceleration: {analysis.trend.acceleration:.4f}")
    lines.append("")

    # Seasonality
    if analysis.seasonality.detected:
        lines.append(
            f"Seasonality: detected with period of {analysis.seasonality.period_days} "
            f"days (strength: {analysis.seasonality.strength:.2f})"
        )
    else:
        lines.append("Seasonality: not detected")
    lines.append("")

    # Anomalies
    anomalies = analysis.anomalies
    lines.append(
        f"Anomalies: {anomalies.anomaly_count} detected out of "
        f"{anomalies.total_points} points (method: {anomalies.method})"
    )
    for a in analysis.anomalies.anomalies[:5]:
        lines.append(f"  - {a.date}: value={a.value:.2f}, score={a.score:.2f}")
    lines.append("")

    # Structural breaks
    if analysis.structural_breaks:
        lines.append(f"Structural breaks: {len(analysis.structural_breaks)} detected")
        for b in analysis.structural_breaks[:5]:
            lines.append(
                f"  - {b.date} (method: {b.method}, confidence: {b.confidence:.2f})"
            )
    else:
        lines.append("Structural breaks: none detected")
    lines.append("")

    # Forecast
    lines.append(f"Forecast horizon: {forecast.horizon} days")
    lines.append(f"Recommended model: {forecast.recommended_model}")
    lines.append("")

    # Model rankings
    if forecast.evaluations:
        lines.append("Model rankings (by MAE):")
        sorted_evals = sorted(forecast.evaluations, key=lambda e: e.mae)
        for e in sorted_evals:
            lines.append(
                f"  - {e.model_name}: MAE={e.mae:.2f}, RMSE={e.rmse:.2f}, "
                f"MAPE={e.mape:.1f}%"
            )
        lines.append("")

    # Recommended model forecast points
    recommended = [
        f for f in forecast.forecasts if f.model_name == forecast.recommended_model
    ]
    if recommended and recommended[0].points:
        pts = recommended[0].points
        first = pts[0]
        last = pts[-1]
        lines.append(f"Forecast ({forecast.recommended_model}):")
        lines.append(
            f"  First point: {first.date} = {first.value:.2f} "
            f"(CI: {first.lower_ci:.2f} to {first.upper_ci:.2f})"
        )
        if len(pts) > 2:
            mid = pts[len(pts) // 2]
            lines.append(
                f"  Mid point: {mid.date} = {mid.value:.2f} "
                f"(CI: {mid.lower_ci:.2f} to {mid.upper_ci:.2f})"
            )
        lines.append(
            f"  Last point: {last.date} = {last.value:.2f} "
            f"(CI: {last.lower_ci:.2f} to {last.upper_ci:.2f})"
        )

    return "\n".join(lines)


def get_prompt(version: str = "default") -> str:
    """Return a prompt template by version name.

    Raises ValueError for unknown versions.
    """
    if version not in PROMPT_REGISTRY:
        raise ValueError(
            f"Unknown prompt version: '{version}'. "
            f"Available: {list(PROMPT_REGISTRY.keys())}"
        )
    return PROMPT_REGISTRY[version]


def build_messages(
    analysis: TrendAnalysis,
    forecast: ForecastComparison,
    version: str = "default",
) -> list[dict]:
    """Build the message list for the Anthropic API.

    Returns [{"role": "system", ...}, {"role": "user", ...}].
    """
    context = format_analysis_context(analysis, forecast)
    template = get_prompt(version)
    user_content = template.format(context=context)

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
