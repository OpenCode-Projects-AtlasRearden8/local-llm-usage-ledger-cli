"""Reports: monthly summaries, per-model totals, trends, and CSV export."""

import csv
import io

from .ledger import month_of

BAR_WIDTH = 40


def _sum_tokens(entries, *fields):
    values = []
    for field in fields:
        values.append(sum(int(e[field]) for e in entries if e.get(field) is not None))
    return values


def monthly_summary(entries, month=None):
    """Aggregate entries into a per-month summary.

    Returns a dict mapping 'YYYY-MM' to stats. Only includes months that
    have at least one entry.
    """
    buckets = {}
    for entry in entries:
        month_key = month_of(entry.get("ts", ""))
        if not month_key:
            continue
        buckets.setdefault(month_key, []).append(entry)
    if month is not None:
        buckets = {k: v for k, v in buckets.items() if k == month}
    summary = {}
    for month_key in sorted(buckets):
        rows = buckets[month_key]
        ok_rows = [e for e in rows if e.get("ok", True)]
        prompt, completion, total = _sum_tokens(
            ok_rows, "prompt_tokens", "completion_tokens", "total_tokens"
        )
        latencies = [
            float(e["latency_ms"]) for e in ok_rows
            if e.get("latency_ms") is not None
        ]
        summary[month_key] = {
            "month": month_key,
            "requests": len(rows),
            "ok_requests": len(ok_rows),
            "failed_requests": len(rows) - len(ok_rows),
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
            "max_latency_ms": int(max(latencies)) if latencies else None,
        }
    return summary


def per_model_totals(entries, month=None):
    """Aggregate token totals per model, optionally within one month."""
    current = None if month is None else month
    seen = {}
    for entry in entries:
        if current is not None and month_of(entry.get("ts", "")) != current:
            continue
        if not entry.get("ok", True):
            continue
        model = entry.get("model") or "(unknown)"
        bucket = seen.setdefault(
            model,
            {
                "model": model,
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )
        bucket["requests"] += 1
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = entry.get(field)
            if value is not None:
                bucket[field] += int(value)
    return [seen[m] for m in sorted(seen)]


def trend_bars(values, max_value=None, width=BAR_WIDTH):
    """Turn a list of (label, value) pairs into ASCII bar rows."""
    if not values:
        return []
    if max_value is None:
        max_value = max((value for _, value in values), default=0)
    max_value = max(max_value, 1)
    rows = []
    for label, value in values:
        filled = int(round((value / max_value) * width))
        bar = "#" * filled + "-" * (width - filled)
        rows.append((label, bar, value))
    return rows


def render_bar_chart(rows, value_col=12):
    lines = ["label".ljust(9) + "chart".ljust(44) + "value".rjust(value_col)]
    for label, bar, value in rows:
        lines.append(label.ljust(9) + bar + "  " + str(value).rjust(value_col - 2))
    return "\n".join(lines)


def format_monthly_table(summary):
    """Render the monthly summary as a plain-text table."""
    if not summary:
        return "No usage recorded yet."
    header = (
        f"{'month':<9} {'requests':>9} {'ok':>6} {'failed':>7} "
        f"{'prompt':>10} {'completion':>11} {'total':>10} "
        f"{'avg ms':>9} {'max ms':>9}"
    )
    lines = [header, "-" * len(header)]
    for stats in summary.values():
        avg = stats["avg_latency_ms"]
        max_ms = stats["max_latency_ms"]
        lines.append(
            f"{stats['month']:<9} {stats['requests']:>9} {stats['ok_requests']:>6} "
            f"{stats['failed_requests']:>7} {stats['prompt_tokens']:>10} "
            f"{stats['completion_tokens']:>11} {stats['total_tokens']:>10} "
            f"{avg if avg is not None else '-':>9} "
            f"{max_ms if max_ms is not None else '-':>9}"
        )
    totals_prompt = sum(s["prompt_tokens"] for s in summary.values())
    totals_completion = sum(s["completion_tokens"] for s in summary.values())
    totals_total = sum(s["total_tokens"] for s in summary.values())
    lines.append("-" * len(header))
    lines.append(
        f"{'TOTAL':<9} {sum(s['requests'] for s in summary.values()):>9} "
        f"{sum(s['ok_requests'] for s in summary.values()):>6} "
        f"{sum(s['failed_requests'] for s in summary.values()):>7} "
        f"{totals_prompt:>10} {totals_completion:>11} {totals_total:>10} "
        f"{'':>9} {'':>9}"
    )
    return "\n".join(lines)


def format_model_table(rows):
    """Render per-model totals as a plain-text table."""
    if not rows:
        return "No successful usage recorded yet."
    header = (
        f"{'model':<32} {'requests':>9} {'prompt':>10} "
        f"{'completion':>11} {'total':>10}"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        lines.append(
            f"{row['model']:<32.32} {row['requests']:>9} {row['prompt_tokens']:>10} "
            f"{row['completion_tokens']:>11} {row['total_tokens']:>10}"
        )
    return "\n".join(lines)


def trend_values(summary, field="total_tokens"):
    return [
        (stats["month"], stats[field])
        for stats in sorted(summary.values(), key=lambda s: s["month"])
    ]


def export_csv(entries, stream=None):
    """Export all ledger entries as CSV. Returns the CSV text."""
    buffer = stream if stream is not None else io.StringIO()
    fields = [
        "ts", "kind", "base_url", "model", "ok", "error", "latency_ms",
        "prompt_tokens", "completion_tokens", "total_tokens",
    ]
    writer = csv.writer(buffer)
    writer.writerow(fields)
    for entry in entries:
        row = [entry.get(field, "") for field in fields]
        writer.writerow(row)
    if stream is None:
        return buffer.getvalue()
    return None
