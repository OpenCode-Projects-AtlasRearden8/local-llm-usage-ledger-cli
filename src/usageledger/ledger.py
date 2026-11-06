"""JSONL ledger: every request is one line, appended in order."""

import datetime
import json
import os
import tempfile


DEFAULT_LEDGER_DIR = os.path.join(".usageledger", "ledger.jsonl")
LEDGER_ENV_VAR = "LOCAL_LLM_LEDGER"


def default_ledger_path():
    return os.environ.get(LEDGER_ENV_VAR) or DEFAULT_LEDGER_DIR


def utc_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    )


def month_of(ts):
    """Convert an ISO timestamp like 2026-05-01T... to '2026-05'."""
    return ts[:7]


def append_entry(path, entry):
    """Append one record to the JSONL ledger, creating parents if needed."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_entries(path):
    """Read all entries; skips blank or corrupt lines without failing hard.

    Returns a list of dicts plus the number of skipped lines, so the
    ledger can keep its 'honest' promise even after a bad write.
    """
    entries = []
    skipped = 0
    if not os.path.exists(path):
        return entries, skipped
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if isinstance(record, dict):
                entries.append(record)
            else:
                skipped += 1
    return entries, skipped


def atomically_write_text(path, text):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=parent or ".", prefix=".tmp-", suffix=".csv"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def make_entry(*, ts, base_url, model, latency_ms, ok=True, error=None,
               prompt_tokens=None, completion_tokens=None, total_tokens=None,
               request_snapshot=None, response_snapshot=None):
    """Build one ledger record with a consistent field order."""
    return {
        "ts": ts,
        "kind": "chat",
        "base_url": base_url,
        "model": model,
        "ok": ok,
        "error": error,
        "latency_ms": latency_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "request_snapshot": request_snapshot,
        "response_snapshot": response_snapshot,
    }
