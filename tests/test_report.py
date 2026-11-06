"""Tests for reporting: summaries, per-model totals, trends, CSV export."""

import csv
import io

from usageledger import report

from tests.helpers import sample_entries


def _summary(entries, month=None):
    return report.monthly_summary(entries, month)


def test_monthly_summary_aggregates_by_month():
    summary = _summary(sample_entries())
    assert sorted(summary) == ["2026-01", "2026-02"]
    jan = summary["2026-01"]
    assert jan["requests"] == 2
    assert jan["ok_requests"] == 1
    assert jan["failed_requests"] == 1
    assert jan["total_tokens"] == 180
    assert jan["prompt_tokens"] == 100
    assert jan["completion_tokens"] == 80


def test_monthly_summary_failure_excluded_from_tokens():
    summary = _summary(sample_entries())
    feb = summary["2026-02"]
    assert feb["failed_requests"] == 0
    assert feb["total_tokens"] == 120


def test_monthly_summary_latency_stats():
    summary = _summary(sample_entries())
    jan = summary["2026-01"]
    assert jan["max_latency_ms"] == 812
    assert jan["avg_latency_ms"] == 812


def test_monthly_summary_single_month_filter():
    summary = _summary(sample_entries(), "2026-01")
    assert list(summary) == ["2026-01"]


def test_monthly_summary_empty():
    assert _summary([]) == {}


def test_per_model_totals():
    rows = report.per_model_totals(sample_entries())
    by_model = {row["model"]: row for row in rows}
    assert by_model["llama3.1:8b"]["total_tokens"] == 180
    assert by_model["llama3.1:8b"]["requests"] == 1
    assert by_model["qwen2.5:7b"]["total_tokens"] == 120


def test_per_model_totals_filtered_by_month():
    rows = report.per_model_totals(sample_entries(), "2026-01")
    assert [row["model"] for row in rows] == ["llama3.1:8b"]


def test_trend_bars_scale_to_max():
    values = [("2026-01", 50), ("2026-02", 100)]
    rows = report.trend_bars(values, width=10)
    label1, bar1, v1 = rows[0]
    label2, bar2, v2 = rows[1]
    assert v1 == 50
    assert bar1.count("#") == 5
    assert bar2.count("#") == 10
    assert len(bar1) == len(bar2) == 10


def test_render_bar_chart_includes_labels_and_values():
    rows = report.trend_bars([("2026-01", 3), ("2026-02", 9)], width=4)
    text = report.render_bar_chart(rows)
    assert "2026-01" in text
    assert "2026-02" in text
    assert "9" in text
    lines = text.splitlines()
    assert lines[0].startswith("label")
    assert len(lines) == 3


def test_format_monthly_table_shows_totals():
    text = report.format_monthly_table(_summary(sample_entries()))
    assert "2026-01" in text
    assert "TOTAL" in text
    assert "180" in text


def test_format_monthly_table_empty():
    assert report.format_monthly_table({}) == "No usage recorded yet."


def test_format_model_table():
    rows = report.per_model_totals(sample_entries())
    text = report.format_model_table(rows)
    assert "llama3.1:8b" in text
    assert "qwen2.5:7b" in text


def test_format_model_table_empty():
    assert "No successful usage" in report.format_model_table([])


def test_export_csv_headers_and_rows():
    entries = sample_entries()
    text = report.export_csv(entries)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    assert rows[0][0] == "ts"
    assert rows[0][-1] == "total_tokens"
    assert len(rows) == len(entries) + 1
    assert rows[1][-1] == "180"


def test_export_csv_escapes_errors():
    entry = dict(sample_entries()[0])
    entry["error"] = 'has, comma "and quotes"'
    text = report.export_csv([entry])
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    assert 'has, comma "and quotes"' in rows[1]
