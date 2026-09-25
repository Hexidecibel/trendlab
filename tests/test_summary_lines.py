"""Plain-English summary lines built from regimes and structural breaks."""

import datetime

import numpy as np

from app.analysis.engine import analyze
from app.analysis.summary import build_summary_lines, format_date, format_rate
from app.models.schemas import DataPoint, Regime, StructuralBreak, TimeSeries

START = datetime.date(2026, 1, 1)


def _ts(values) -> TimeSeries:
    return TimeSeries(
        source="t",
        query="q",
        points=[
            DataPoint(date=START + datetime.timedelta(days=i), value=float(v))
            for i, v in enumerate(values)
        ],
    )


def _regime(start_idx, end_idx, slope):
    return Regime(
        start_date=str(START + datetime.timedelta(days=start_idx)),
        end_date=str(START + datetime.timedelta(days=end_idx)),
        label="rising",
        mean_value=100.0,
        mean_return=0.0,
        volatility=0.0,
        slope_pct_per_month=slope,
    )


class TestFormatting:
    def test_format_date(self):
        assert format_date(datetime.date(2026, 3, 3)) == "Mar 3, 2026"
        assert format_date("2026-01-05") == "Jan 5, 2026"

    def test_format_rate(self):
        assert format_rate(8.04) == "+8%/mo"
        assert format_rate(2.0) == "+2%/mo"
        assert format_rate(-1.54) == "-1.5%/mo"
        assert format_rate(12.6) == "+13%/mo"


class TestBuildSummaryLines:
    def test_growth_slowed(self):
        ts = _ts(np.linspace(100, 200, 120))
        brk = StructuralBreak(
            date=START + datetime.timedelta(days=61),
            index=61,
            method="cusum",
            confidence=1.0,
        )
        regimes = [_regime(0, 60, 8.0), _regime(61, 119, 2.0)]
        lines = build_summary_lines(ts, [brk], regimes)
        assert lines == ["Growth slowed from +8%/mo to +2%/mo after Mar 3, 2026"]

    def test_drop_reported(self):
        values = [100.0] * 60 + [65.0] * 60
        ts = _ts(values)
        brk = StructuralBreak(
            date=START + datetime.timedelta(days=60),
            index=60,
            method="cusum",
            confidence=1.0,
        )
        regimes = [_regime(0, 59, 0.0), _regime(60, 119, 0.0)]
        lines = build_summary_lines(ts, [brk], regimes)
        assert lines == ["Dropped 35% around Mar 2, 2026"]

    def test_jump_date_pinned_to_step_and_no_fake_reversal(self):
        # CUSUM-style break on the last pre-step point (index 59)
        values = list(np.linspace(100, 110, 60)) + [65.0] * 60
        ts = _ts(values)
        brk = StructuralBreak(
            date=START + datetime.timedelta(days=59),
            index=59,
            method="cusum",
            confidence=1.0,
        )
        regimes = [_regime(0, 58, 5.0), _regime(59, 119, -40.0)]
        lines = build_summary_lines(ts, [brk], regimes)
        assert lines == ["Dropped 41% around Mar 2, 2026"]

    def test_max_four_most_significant_first(self):
        ts = _ts(np.linspace(100, 200, 200))
        slopes = [2.0, 30.0, 3.0, 25.0, 1.0, 40.0]
        regimes = [
            _regime(i * 30, i * 30 + 29, s) for i, s in enumerate(slopes)
        ]
        lines = build_summary_lines(ts, [], regimes)
        assert 1 <= len(lines) <= 4
        # Biggest slope change (+1 -> +40) is first
        assert "+40%/mo" in lines[0]

    def test_single_regime_overall_line(self):
        ts = _ts(np.linspace(100, 130, 60))
        regimes = [_regime(0, 59, 13.0)]
        lines = build_summary_lines(ts, [], regimes)
        assert lines == ["Steady growth of about +13%/mo over the period"]

    def test_empty(self):
        assert build_summary_lines(_ts([]), [], []) == []


class TestAnalyzeIntegration:
    def test_step_series_mentions_jump(self):
        values = [10.0] * 50 + [50.0] * 50
        result = analyze(_ts(values))
        assert result.summary_lines
        assert any(line.startswith("Jumped") for line in result.summary_lines)
        assert len(result.summary_lines) <= 4

    def test_regimes_carry_slope(self):
        result = analyze(_ts(np.linspace(100, 200, 90)))
        assert all(r.slope_pct_per_month is not None for r in result.regimes)
