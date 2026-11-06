# STATUS.md — local-llm-usage-ledger-cli

## What was built

`usageledger` — a Python CLI that keeps an honest ledger of your local-AI
usage. It wraps calls to **any OpenAI-compatible endpoint** (default:
Ollama at `http://localhost:11434/v1`; any other `base_url` via flag or
`LOCAL_LLM_BASE_URL`) and logs every request to a JSONL ledger, then reports
on it. It never asks for or sends an API key — there is no auth logic at all,
and a test proves no Authorization header is sent even when common API-key
environment variables are set.

### Features

- **`chat`** — one chat turn; logs timestamp (UTC ISO), base URL, model,
  token counts from the server's reported usage, latency in ms, success/error
  flag, and compact request/response snapshots (content truncated to ~300
  chars; long system prompts summarized as character counts, not stored).
  Failed calls are logged too, with the error text.
- **`month [YYYY-MM]`** — monthly summary table: requests, ok/failed,
  prompt/completion/total tokens, avg/max latency, with a TOTAL row.
- **`models [YYYY-MM]`** — per-model totals.
- **`trend [--field ...]`** — plain-text ASCII bar chart of monthly
  totals (tokens or request counts).
- **`log [N]`** — the N most recent ledger entries; reports skipped lines.
- **`export PATH`** — full ledger to CSV (written atomically).
- Corrupt/blank ledger lines are skipped and counted, not fatal.
- Zero runtime dependencies (stdlib only); Python 3.9+.

## How to run it

```sh
pip install .                 # installs the `usageledger` command
# or: pip install -e ".[dev]"

usageledger chat "Tell me something useful."          # logs to .usageledger/ledger.jsonl
usageledger month
usageledger models
usageledger trend
usageledger log 20
usageledger export usage.csv

# Point anywhere else:
usageledger chat "hi" -u http://localhost:1234/v1 -m qwen2.5 --system "Be friendly."
```

Env vars: `LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL` (default `llama3.1`),
`LOCAL_LLM_LEDGER`. Also runnable without installing:
`PYTHONPATH=src python3 -m usageledger ...`.

## Project layout

```
src/usageledger/
  client.py      OpenAI-compatible HTTP client (stdlib urllib, no auth)
  ledger.py      JSONL ledger read/append, tolerant of corrupt lines
  snapshots.py   compact request/response snapshots
  report.py      summaries, per-model totals, trend bars, CSV export
  cli.py         argparse CLI (chat, month, models, trend, log, export)
tests/           pytest suite, HTTP layer fully mocked
```

## Verification results

- **pytest: 53 passed, 0 failed** — covers client (URL/payload construction,
  usage/reply parsing, HTTP/URL/non-JSON error wrapping, and the no-key
  promise), ledger round-trips and corrupt-line tolerance, snapshots size and
  truncation, reports (aggregation, month filter, scaling/trend bars, CSV
  escaping), and six CLI commands end-to-end against mocked endpoints,
  including failure logging and env-var precedence.
- **Real end-to-end smoke test** — ran a mock OpenAI-compatible HTTP server
  on localhost and exercised every command: chat (reply + `[logged: ...]`
  line), month/models/trend/log reports, CSV export, and the failure path
  (connection refused → error entry logged, exit code 1).
- **Packaging verified** — `pip install .` in a clean venv builds fine and the
  `usageledger` console script works (`--version`, `--help`, `month`).
  Full test suite also passes inside that venv.

## Known gaps

- Token counts rely on the server's reported `usage`; servers that omit it
  (some need `stream_options` or ignore `max_tokens` semantics) yield blank
  token fields rather than estimates — intentionally honest, not guessed.
- Non-streaming chat only; `/v1/completions` (legacy) and embeddings are not
  wrapped, though the ledger format would extend to them.
- No pruning/rotation of the ledger file; it grows without bound.
- Trend chart assumes one month label per month; very long histories render
  one row per month (no automatic windowing).
- CSV `ok` column serializes booleans as `True`/`False` (Python style).
- The sibling projects named in the README (microscan-local-chat-speed-cli,
  mini-model-bench-cli) are referenced as comparison context; their URLs are
  placeholders and may not exist.

## Privacy

Local-first: the ledger is a plain JSONL file you own; snapshots are
truncated and system prompts are summarized rather than stored; no API keys,
no telemetry, no secrets in the repository.
