"""Command-line interface for usageledger.

Plain-text, honest accounting of local-AI usage. No API keys, no cloud.
"""

import argparse
import os
import sys
import time

from . import __version__, client, ledger, report, snapshots

ENV_BASE_URL = "LOCAL_LLM_BASE_URL"
ENV_MODEL = "LOCAL_LLM_MODEL"

BANNER = "usageledger: an honest ledger of your local-AI usage"


def _default_base_url():
    return os.environ.get(ENV_BASE_URL) or client.DEFAULT_BASE_URL


def _default_model():
    return os.environ.get(ENV_MODEL) or "llama3.1"


def _ledger_path(args):
    return args.ledger or ledger.default_ledger_path()


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="usageledger",
        description=BANNER
        + ". Wraps any OpenAI-compatible endpoint (never sends an API key), "
        "logs every request to JSONL, and reports usage.",
        epilog="Env vars: LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL, LOCAL_LLM_LEDGER",
    )
    parser.add_argument(
        "--version", action="version", version=f"usageledger {__version__}"
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--base-url", "-u", default=None, metavar="URL",
        help="OpenAI-compatible endpoint base URL "
             "(default: $LOCAL_LLM_BASE_URL or %s)" % client.DEFAULT_BASE_URL,
    )
    common.add_argument(
        "--ledger", default=None, metavar="PATH",
        help="JSONL ledger path (default: .usageledger/ledger.jsonl "
             "or $LOCAL_LLM_LEDGER)",
    )

    subs = parser.add_subparsers(dest="command")

    p_chat = subs.add_parser(
        "chat", parents=[common],
        help="Send one chat turn and log it",
        description="Send one prompt to the endpoint and log the request. "
        "The reply is printed, and an entry is appended to the ledger "
        "whether the call succeeds or fails.",
    )
    p_chat.add_argument("prompt", help="The user prompt text")
    p_chat.add_argument(
        "--model", "-m", default=None, metavar="NAME",
        help="Model name to request (default: $LOCAL_LLM_MODEL or %s)"
             % _default_model(),
    )
    p_chat.add_argument(
        "--system", default=None, metavar="TEXT",
        help="Optional system prompt",
    )
    p_chat.add_argument(
        "--max-tokens", type=int, default=None,
        help="Optional completion token limit passed through to the server",
    )
    p_chat.add_argument(
        "--temperature", type=float, default=None,
        help="Optional sampling temperature passed through to the server",
    )
    p_chat.add_argument(
        "--timeout", type=int, default=client.DEFAULT_TIMEOUT,
        help="HTTP timeout in seconds (default: %(default)s)",
    )
    p_chat.add_argument(
        "--raw", action="store_true",
        help="Print the full raw JSON response instead of just the reply",
    )

    p_month = subs.add_parser(
        "month", parents=[common],
        help="Show a monthly usage summary",
        description="Show request counts and token totals per month.",
    )
    p_month.add_argument(
        "month", nargs="?", default=None, metavar="YYYY-MM",
        help="Limit the summary to a single month, e.g. 2026-05",
    )

    p_models = subs.add_parser(
        "models", parents=[common],
        help="Show per-model totals",
        description="Show request counts and token totals per model.",
    )
    p_models.add_argument(
        "month", nargs="?", default=None, metavar="YYYY-MM",
        help="Limit the totals to a single month",
    )

    p_trend = subs.add_parser(
        "trend", parents=[common],
        help="Show a plain-text trend chart",
        description="Plot monthly totals as ASCII bars.",
    )
    p_trend.add_argument(
        "--field", default="total_tokens",
        choices=["total_tokens", "prompt_tokens", "completion_tokens",
                 "requests"],
        help="Which value to chart (default: %(default)s)",
    )

    p_log = subs.add_parser(
        "log", parents=[common],
        help="Show recent ledger entries",
        description="Show the most recent ledger entries.",
    )
    p_log.add_argument(
        "count", nargs="?", type=int, default=10,
        help="How many entries to show (default: %(default)s)",
    )

    p_export = subs.add_parser(
        "export", parents=[common],
        help="Export the ledger to CSV",
        description="Write every ledger entry to a CSV file.",
    )
    p_export.add_argument("path", help="CSV file path to write")

    return parser


def _resolve_chat_args(args):
    base_url = args.base_url or _default_base_url()
    model = args.model or _default_model()
    return base_url, model


def _build_messages(args):
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})
    return messages


def cmd_chat(args, out=None, err=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    base_url, model = _resolve_chat_args(args)
    messages = _build_messages(args)
    request_snapshot = {
        "base_url": base_url,
        "model": model,
        "messages": snapshots.compact_messages(messages),
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }
    started = time.perf_counter()
    ts = None
    try:
        response = client.chat_completions(
            base_url, model, messages,
            timeout=args.timeout,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        prompt_tokens, completion_tokens, total_tokens = client.parse_usage(
            response
        )
        reply = client.parse_reply(response)
        entry = ledger.make_entry(
            ts=ledger.utc_now_iso(),
            base_url=base_url,
            model=model,
            latency_ms=latency_ms,
            ok=True,
            error=None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            request_snapshot=request_snapshot,
            response_snapshot=snapshots.compact_response(response),
        )
        ledger.append_entry(_ledger_path(args), entry)
        if args.raw:
            import json
            out.write(json.dumps(response, indent=2, ensure_ascii=False) + "\n")
        else:
            out.write(reply.rstrip() + "\n")
        out.write(
            f"\n[logged: {model}, {total_tokens or '?'} tokens, "
            f"{latency_ms} ms -> {_ledger_path(args)}]\n"
        )
        return 0
    except (client.LLMError, OSError, ValueError) as exc:
        latency_ms = round((time.perf_counter() - started) * 1000)
        entry = ledger.make_entry(
            ts=ledger.utc_now_iso(),
            base_url=base_url,
            model=model,
            latency_ms=latency_ms,
            ok=False,
            error=str(exc),
            request_snapshot=request_snapshot,
        )
        ledger.append_entry(_ledger_path(args), entry)
        err.write(f"error: {exc}\n")
        err.write(
            f"[logged failure: {model}, {latency_ms} ms -> {_ledger_path(args)}]\n"
        )
        return 1


def cmd_month(args, out=None):
    out = sys.stdout if out is None else out
    entries, skipped = ledger.read_entries(_ledger_path(args))
    summary = report.monthly_summary(entries, args.month)
    if skipped:
        out.write(f"(skipped {skipped} unreadable ledger lines)\n")
    out.write(report.format_monthly_table(summary) + "\n")
    return 0


def cmd_models(args, out=None):
    out = sys.stdout if out is None else out
    entries, _ = ledger.read_entries(_ledger_path(args))
    rows = report.per_model_totals(entries, args.month)
    out.write(report.format_model_table(rows) + "\n")
    return 0


def cmd_trend(args, out=None):
    out = sys.stdout if out is None else out
    entries, _ = ledger.read_entries(_ledger_path(args))
    summary = report.monthly_summary(entries)
    rows = report.trend_bars(report.trend_values(summary, args.field))
    if not rows:
        out.write("No usage recorded yet.\n")
        return 0
    titles = {
        "total_tokens": "total tokens per month",
        "prompt_tokens": "prompt tokens per month",
        "completion_tokens": "completion tokens per month",
        "requests": "requests per month",
    }
    out.write(titles[args.field] + "\n")
    out.write(report.render_bar_chart(rows) + "\n")
    return 0


def cmd_log(args, out=None):
    out = sys.stdout if out is None else out
    entries, skipped = ledger.read_entries(_ledger_path(args))
    if args.count >= 0:
        entries = entries[-args.count:] if args.count else []
    header = (
        f"{'timestamp':<20} {'model':<28} {'ok':>3} {'ms':>8} "
        f"{'prompt':>8} {'completion':>11} {'total':>9}"
    )
    lines = [header, "-" * len(header)]
    for entry in entries:
        lines.append(
            f"{entry.get('ts', '?'):<20.20} {entry.get('model', '?'):<28.28} "
            f"{'y' if entry.get('ok', True) else 'n':>3} "
            f"{entry.get('latency_ms', ''):>8} "
            f"{entry.get('prompt_tokens') or '':>8} "
            f"{entry.get('completion_tokens') or '':>11} "
            f"{entry.get('total_tokens') or '':>9}"
        )
    if skipped:
        lines.append(f"(skipped {skipped} unreadable ledger lines)")
    out.write("\n".join(lines) + "\n")
    return 0


def cmd_export(args, out=None):
    out = sys.stdout if out is None else out
    entries, _ = ledger.read_entries(_ledger_path(args))
    csv_text = report.export_csv(entries)
    ledger.atomically_write_text(args.path, csv_text)
    out.write(f"Wrote {len(entries)} entries to {args.path}\n")
    return 0


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    handlers = {
        "chat": cmd_chat,
        "month": cmd_month,
        "models": cmd_models,
        "trend": cmd_trend,
        "log": cmd_log,
        "export": cmd_export,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
