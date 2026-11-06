"""Tests for the JSONL ledger and compact snapshots."""

import json

from usageledger import ledger, snapshots

from tests.helpers import sample_entries


def test_append_and_read_roundtrip(tmp_path):
    path = tmp_path / "ledger.jsonl"
    entry = ledger.make_entry(
        ts="2026-05-01T00:00:00+00:00",
        base_url="http://localhost:11434/v1",
        model="llama3.1",
        latency_ms=100,
        total_tokens=46,
    )
    ledger.append_entry(str(path), entry)
    entries, skipped = ledger.read_entries(str(path))
    assert skipped == 0
    assert len(entries) == 1
    assert entries[0]["model"] == "llama3.1"
    assert entries[0]["kind"] == "chat"


def test_append_creates_parent_dirs(tmp_path):
    path = tmp_path / "a" / "b" / "ledger.jsonl"
    ledger.append_entry(str(path), {"ts": "x"})
    assert path.exists()


def test_missing_ledger_reads_empty(tmp_path):
    entries, skipped = ledger.read_entries(str(tmp_path / "nope.jsonl"))
    assert entries == []
    assert skipped == 0


def test_blank_and_corrupt_lines_are_skipped(tmp_path):
    path = tmp_path / "ledger.jsonl"
    good1 = sample_entries()[0]
    good2 = sample_entries()[2]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(good1) + "\n")
        handle.write("\n")
        handle.write("{not valid json\n")
        handle.write(json.dumps(good2) + "\n")
        handle.write("[1,2,3]\n")
    entries, skipped = ledger.read_entries(str(path))
    assert len(entries) == 2
    assert skipped == 2


def test_entry_field_order_and_defaults():
    entry = ledger.make_entry(
        ts="2026-05-01T00:00:00+00:00",
        base_url="http://localhost:11434/v1",
        model="m",
        latency_ms=10,
    )
    assert entry["ok"] is True
    assert entry["error"] is None
    assert entry["prompt_tokens"] is None
    assert list(entry.keys())[:3] == ["ts", "kind", "base_url"]


def test_month_of():
    assert ledger.month_of("2026-05-17T10:00:00+00:00") == "2026-05"


def test_atomically_write_text(tmp_path):
    path = tmp_path / "out.csv"
    ledger.atomically_write_text(str(path), "a,b\n1,2\n")
    assert path.read_text(encoding="utf-8") == "a,b\n1,2\n"
    leftovers = [p for p in tmp_path.iterdir() if p.name != "out.csv"]
    assert leftovers == []


def test_env_override_of_default_path(monkeypatch, tmp_path):
    path = tmp_path / "env-ledger.jsonl"
    monkeypatch.setenv(ledger.LEDGER_ENV_VAR, str(path))
    assert ledger.default_ledger_path() == str(path)


def test_compact_messages_snapshot():
    messages = [
        {"role": "system", "content": "A" * 500},
        {"role": "user", "content": "B" * 400},
    ]
    out = snapshots.compact_messages(messages)
    system = out[0]
    user = out[1]
    assert system["content"] == "(system prompt omitted; 500 characters)"
    assert user["content"].endswith(snapshots.TRUNCATION_NOTE)
    assert len(user["content"]) <= snapshots.SNAPSHOT_CONTENT_LIMIT + 20


def test_compact_response_snapshot():
    response = {
        "model": "llama3.1",
        "choices": [
            {"message": {"content": "C" * 1000}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    }
    snap = snapshots.compact_response(response)
    assert snap["usage"] == {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}
    assert snap["finish_reason"] == "stop"
    assert snap["reply"].endswith(snapshots.TRUNCATION_NOTE)
    assert snap["model_reported"] == "llama3.1"


def test_snapshots_stay_small():
    response = {
        "choices": [{"message": {"content": "x" * 100000}, "finish_reason": "stop"}],
        "usage": {},
    }
    snap = snapshots.compact_response(response)
    assert len(json.dumps(snap)) < 600
