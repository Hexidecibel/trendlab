"""PDF export service for generating analysis reports."""

import io
from datetime import datetime

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.schemas import ForecastComparison, TimeSeries, TrendAnalysis

# Use non-interactive backend for server-side rendering
matplotlib.use("Agg")


def _create_chart_image(
    series: TimeSeries,
    forecast: ForecastComparison,
    model_name: str,
) -> io.BytesIO:
    """Generate a matplotlib chart and return as image bytes."""
    fig: Figure = plt.figure(figsize=(8, 4), dpi=100)
    ax = fig.add_subplot(111)

    # Plot actual data
    dates = [p.date for p in series.points]
    values = [p.value for p in series.points]
    ax.plot(dates, values, label="Actual", color="#3b82f6", linewidth=2)

    # Find the selected model forecast
    model_forecast = next(
        (f for f in forecast.forecasts if f.model_name == model_name), None
    )
    if model_forecast:
        f_dates = [p.date for p in model_forecast.points]
        f_values = [p.value for p in model_forecast.points]
        f_upper = [p.upper_ci for p in model_forecast.points]
        f_lower = [p.lower_ci for p in model_forecast.points]

        ax.plot(
            f_dates, f_values, label=f"Forecast ({model_name})", color="#f97316",
            linewidth=2, linestyle="--"
        )
        ax.fill_between(f_dates, f_lower, f_upper, alpha=0.1, color="#f97316")

    ax.set_xlabel("Date")
    ax.set_ylabel("Value")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


def generate_pdf_report(
    series: TimeSeries,
    analysis: TrendAnalysis,
    forecast: ForecastComparison,
    insight_text: str | None = None,
) -> io.BytesIO:
    """Generate a PDF report for the analysis."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        spaceAfter=20,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10,
    )
    body_style = styles["Normal"]

    elements = []

    # Title
    title = f"{series.source.upper()}: {series.query}"
    elements.append(Paragraph(title, title_style))
    elements.append(
        Paragraph(
            f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}",
            body_style,
        )
    )
    elements.append(Spacer(1, 20))

    # Summary Statistics
    elements.append(Paragraph("Summary Statistics", heading_style))

    values = [p.value for p in series.points]
    stats_data = [
        ["Metric", "Value"],
        ["Data Points", str(len(series.points))],
        ["Date Range", f"{series.points[0].date} to {series.points[-1].date}"],
        ["Min Value", f"{min(values):,.2f}"],
        ["Max Value", f"{max(values):,.2f}"],
        ["Mean Value", f"{sum(values) / len(values):,.2f}"],
    ]

    stats_table = Table(stats_data, colWidths=[2.5 * inch, 3.5 * inch])
    stats_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 11),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ]
        )
    )
    elements.append(stats_table)
    elements.append(Spacer(1, 15))

    # Trend Analysis
    elements.append(Paragraph("Trend Analysis", heading_style))

    trend_data = [
        ["Aspect", "Result"],
        ["Direction", analysis.trend.direction.title()],
        ["Momentum", f"{analysis.trend.momentum:.4f}"],
        ["Acceleration", f"{analysis.trend.acceleration:.4f}"],
        [
            "Seasonality",
            f"Yes ({analysis.seasonality.period_days} days)"
            if analysis.seasonality.detected
            else "Not detected",
        ],
        ["Anomalies", f"{analysis.anomalies.anomaly_count} detected"],
        ["Structural Breaks", f"{len(analysis.structural_breaks)} detected"],
    ]

    trend_table = Table(trend_data, colWidths=[2.5 * inch, 3.5 * inch])
    trend_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 11),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ]
        )
    )
    elements.append(trend_table)
    elements.append(Spacer(1, 15))

    # Chart
    elements.append(Paragraph("Time Series Chart", heading_style))
    chart_buf = _create_chart_image(series, forecast, forecast.recommended_model)
    img = Image(chart_buf, width=6.5 * inch, height=3.25 * inch)
    elements.append(img)
    elements.append(Spacer(1, 15))

    # Forecast Table
    elements.append(Paragraph("Forecast Comparison", heading_style))

    forecast_header = ["Model", "MAE", "RMSE", "MAPE", "Recommended"]
    forecast_rows = [forecast_header]

    for ev in forecast.evaluations:
        is_recommended = "Yes" if ev.model_name == forecast.recommended_model else ""
        forecast_rows.append(
            [
                ev.model_name,
                f"{ev.mae:.2f}",
                f"{ev.rmse:.2f}",
                f"{ev.mape:.1f}%",
                is_recommended,
            ]
        )

    col_widths = [1.5 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 1.5 * inch]
    forecast_table = Table(forecast_rows, colWidths=col_widths)
    forecast_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 11),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ]
        )
    )
    elements.append(forecast_table)
    elements.append(Spacer(1, 15))

    # AI Insight (if available)
    if insight_text:
        elements.append(Paragraph("AI Analysis", heading_style))
        # Clean up markdown for PDF
        clean_text = insight_text.replace("**", "").replace("*", "").replace("#", "")
        for para in clean_text.split("\n\n"):
            if para.strip():
                elements.append(Paragraph(para.strip(), body_style))
                elements.append(Spacer(1, 8))

    # Footer
    elements.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        "Footer",
        parent=body_style,
        fontSize=8,
        textColor=colors.grey,
    )
    elements.append(
        Paragraph(
            "Generated by TrendLab - AI-powered trend analysis platform",
            footer_style,
        )
    )

    doc.build(elements)
    buffer.seek(0)
    return buffer
