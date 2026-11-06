"""End-to-end CLI tests with mocked endpoints and a temp ledger."""

import csv
import json

import pytest

import usageledger.cli as cli
from usageledger.client import LLMError
from tests.helpers import FakeHttp, ok_response, sample_entries


def _run(argv):
    return cli.main(argv)


@pytest.fixture
def ledger_path(tmp_path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    monkeypatch.setenv("LOCAL_LLM_LEDGER", str(path))
    return path


@pytest.fixture
def no_env_defaults(monkeypatch):
    monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_LLM_MODEL", raising=False)


def test_chat_success_logs_entry(monkeypatch, ledger_path, no_env_defaults, capsys):
    fake = FakeHttp()
    monkeypatch.setattr(cli.client, "http_post_json", fake)
    rc = _run(["chat", "Tell me about ledes.", "--model", "llama3.1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "How can I help" in out
    assert "[logged: llama3.1, 46 tokens" in out
    entries = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["ok"] is True
    assert entry["total_tokens"] == 46
    assert entry["base_url"] == cli.client.DEFAULT_BASE_URL
    assert entry["model"] == "llama3.1"
    assert entry["request_snapshot"]["messages"][0]["role"] == "user"
    assert entry["response_snapshot"]["reply"].endswith("How can I help?")
    payload = fake.calls[0]["payload"]
    assert payload["model"] == "llama3.1"
    assert "Authorization" not in json.dumps(payload)


def test_chat_failure_still_logged(monkeypatch, ledger_path, no_env_defaults, capsys):
    fake = FakeHttp(error=LLMError("Connection refused: is Ollama running?"))
    monkeypatch.setattr(cli.client, "http_post_json", fake)
    rc = _run(["chat", "hi"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Connection refused" in err
    entries = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    assert len(entries) == 1
    assert entries[0]["ok"] is False
    assert "Ollama" in entries[0]["error"]


def test_chat_uses_env_defaults(monkeypatch, ledger_path, capsys):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://localhost:9999/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen2.5")
    fake = FakeHttp()
    monkeypatch.setattr(cli.client, "http_post_json", fake)
    rc = _run(["chat", "hello"])
    assert rc == 0
    entry = json.loads(ledger_path.read_text().splitlines()[0])
    assert entry["base_url"] == "http://localhost:9999/v1"
    assert entry["model"] == "qwen2.5"


def test_chat_flag_beats_env(monkeypatch, ledger_path, capsys):
    monkeypatch.setenv("LOCAL_LLM_MODEL", "env-model")
    fake = FakeHttp()
    monkeypatch.setattr(cli.client, "http_post_json", fake)
    rc = _run(["chat", "hello", "--model", "flag-model"])
    assert rc == 0
    entry = json.loads(ledger_path.read_text().splitlines()[0])
    assert entry["model"] == "flag-model"


def test_chat_system_prompt_is_summarized_in_snapshot(
    monkeypatch, ledger_path, no_env_defaults, capsys
):
    fake = FakeHttp()
    monkeypatch.setattr(cli.client, "http_post_json", fake)
    long_system = "You are a wonderful tutor. " * 20
    rc = _run(["chat", "hello", "--system", long_system])
    assert rc == 0
    entry = json.loads(ledger_path.read_text().splitlines()[0])
    system_snapshot = entry["request_snapshot"]["messages"][0]
    assert system_snapshot["role"] == "system"
    assert long_system not in json.dumps(entry)
    assert "omitted" in system_snapshot["content"]
    payload = fake.calls[0]["payload"]
    assert payload["messages"][0]["content"] == long_system


def test_month_command(monkeypatch, ledger_path, no_env_defaults, capsys):
    ledger_path.write_text(
        "".join(
            json.dumps(e) + "\n" for e in sample_entries()
        ),
        encoding="utf-8",
    )
    rc = _run(["month"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "2026-01" in out
    assert "2026-02" in out
    assert "180" in out
    assert "TOTAL" in out


def test_month_command_single_month(
    monkeypatch, ledger_path, no_env_defaults, capsys
):
    ledger_path.write_text(
        "".join(json.dumps(e) + "\n" for e in sample_entries()),
        encoding="utf-8",
    )
    rc = _run(["month", "2026-02"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "2026-01" not in out
    assert "2026-02" in out


def test_models_command(monkeypatch, ledger_path, no_env_defaults, capsys):
    ledger_path.write_text(
        "".join(json.dumps(e) + "\n" for e in sample_entries()),
        encoding="utf-8",
    )
    rc = _run(["models"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "llama3.1:8b" in out
    assert "qwen2.5:7b" in out


def test_trend_command(monkeypatch, ledger_path, no_env_defaults, capsys):
    ledger_path.write_text(
        "".join(json.dumps(e) + "\n" for e in sample_entries()),
        encoding="utf-8",
    )
    rc = _run(["trend"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "#" in out or "-" in out
    assert "2026-01" in out
    assert "2026-02" in out


def test_trend_command_empty(monkeypatch, ledger_path, no_env_defaults, capsys):
    rc = _run(["trend"])
    assert rc == 0
    assert "No usage recorded yet." in capsys.readouterr().out


def test_log_command(monkeypatch, ledger_path, no_env_defaults, capsys):
    ledger_path.write_text(
        "".join(json.dumps(e) + "\n" for e in sample_entries()),
        encoding="utf-8",
    )
    rc = _run(["log", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "2026-02-02" in out
    assert "2026-01-05" not in out


def test_log_shows_skip_count(monkeypatch, ledger_path, no_env_defaults, capsys):
    ledger_path.write_text(
        json.dumps(sample_entries()[0]) + "\n{broken\n",
        encoding="utf-8",
    )
    rc = _run(["log"])
    assert rc == 0
    assert "skipped 1" in capsys.readouterr().out


def test_export_command(monkeypatch, ledger_path, tmp_path, no_env_defaults, capsys):
    ledger_path.write_text(
        "".join(json.dumps(e) + "\n" for e in sample_entries()),
        encoding="utf-8",
    )
    csv_path = tmp_path / "usage.csv"
    rc = _run(["export", str(csv_path)])
    assert rc == 0
    assert csv_path.exists()
    with open(csv_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][0] == "ts"
    assert len(rows) == 4
    out = capsys.readouterr().out
    assert "Wrote 3 entries" in out


def test_no_version_flag_leads_to_help():
    with pytest.raises(SystemExit) as excinfo:
        _run(["--version"])
    assert excinfo.value.code == 0


def test_missing_command_prints_help(capsys):
    rc = _run([])
    assert rc == 0
    assert "usageledger" in capsys.readouterr().out
