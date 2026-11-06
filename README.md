# usageledger — local LLM usage ledger CLI

A Python CLI that keeps an **honest ledger of your local-AI usage**. It wraps
calls to **any OpenAI-compatible endpoint** (by default, Ollama at
`http://localhost:11434/v1`), logs every request to a JSONL file, and reports
monthly summaries, per-model totals, and trend charts — all in plain text,
plus CSV export.

It never asks for an API key. It is built for local servers like Ollama,
llama.cpp, LM Studio, and vLLM, but it will happily point at any OpenAI-compatible
`base_url` you give it — and still *never* sends a key or captures one from the
environment. Pointing `--base-url` at a remote endpoint works fine; usageledger
simply sends the model, your messages, and nothing else.

Part of the Asdale Dynamics, LLC family of friendly, local-first AI tools.
Living at the intersection of a nurse-turned-AI-author's plain-English style
and a bookworm's love of records: think of usageledger as the receipt book for
your local model habit.

## Why "honest"?

Many usage tools estimate after the fact. usageledger logs *each request as it
happens*, in one JSON line:

- ISO timestamp (UTC)
- model name and base URL
- token counts, straight from the server's reported usage
- latency in milliseconds
- a **compact snapshot** of the request and response (a few hundred characters,
  so the ledger stays small and private)
- an explicit ok/error flag — failed calls are logged too, with the error text

Corrupt or blank ledger lines are skipped (and counted) rather than crashing
your reports. The ledger stays usable even after a bad write.

## Install

No third-party dependencies. Python 3.9+.

```sh
pip install .
```

This installs a `usageledger` command. For development:

```sh
pip install -e ".[dev]"
```

## Quick start

```sh
# One chat turn against local Ollama (default base_url), logged automatically
usageledger chat "Explain zero-knowledge proofs like a friend would."
```

Output shows the reply, then a line like:

```
[logged: llama3.1, 214 tokens, 812 ms -> .usageledger/ledger.jsonl]
```

### Reports

```sh
usageledger month                # monthly summary table (all months)
usageledger month 2026-05        # summary for one month
usageledger models               # totals per model
usageledger models 2026-05       # totals per model within a month
usageledger trend                # ASCII bar chart: total tokens per month
usageledger trend --field requests
usageledger log 20               # 20 most recent ledger entries
usageledger export usage.csv     # full ledger as CSV
```

### Pointing somewhere else

```sh
usageledger chat "hello" \
  --base-url http://localhost:1234/v1 \
  --model qwen2.5-7b-instruct \
  --system "You are a friendly, plain-English tutor."
```

Defaults come from the environment when flags are absent:

| Variable             | Meaning                                  | Default                          |
| -------------------- | ---------------------------------------- | -------------------------------- |
| `LOCAL_LLM_BASE_URL` | OpenAI-compatible base URL               | `http://localhost:11434/v1` (Ollama) |
| `LOCAL_LLM_MODEL`    | model name to request                    | `llama3.1`                       |
| `LOCAL_LLM_LEDGER`   | JSONL ledger path                        | `.usageledger/ledger.jsonl`      |

Extra knobs: `--max-tokens`, `--temperature`, `--timeout` (seconds),
`--raw` (print the full JSON response).

Note: Ollama's OpenAI-compatible endpoint lives at `http://localhost:11434/v1`
(and it also exposes `/v1/models`). Other servers: llama.cpp `http://localhost:8080/v1`,
LM Studio `http://localhost:1234/v1`, vLLM `http://localhost:8000/v1`.
Some servers report token usage only when asked; Ollama includes it.
If a server omits `usage`, the ledger records blanks rather than guessing —
the ledger stays honest.

## What stays private

- Everything is local. The ledger is a plain JSONL file you own.
- Snapshots truncate to a few hundred characters. Long system prompts are
  summarized as "(system prompt omitted; N characters)" instead of being stored.
- No keys, no telemetry, no network calls beyond the endpoint you choose.

## How it relates to its cousins

- **microscan-local-chat-speed-cli** — one-shot *speed* of a local model.
- **mini-model-bench-cli** — *quality* comparisons between models.
- **usageledger** (this tool) — the *behavioral accounting*: what you actually
  used, when, and how much, month over month.

## Development

```sh
pip install -e ".[dev]"
pytest            # mocked-endpoint tests; no server needed
```

The HTTP layer is mocked in tests, so the suite runs without any model
server running. To smoke-test for real against Ollama:

```sh
python -m usageledger chat "ping"
python -m usageledger month
```

## Sibling projects

- [microscan-local-chat-speed-cli](https://github.com/DylanAsdale/microscan-local-chat-speed-cli) — one-shot speed of a local model
- [mini-model-bench-cli](https://github.com/DylanAsdale/mini-model-bench-cli) — quality comparisons between models

## Author & license

Built by Asdale Dynamics, LLC — Dylan Asdale, The Massive AI Manual,
[dylanasdale.github.io](https://dylanasdale.github.io). Friendly sample tests,
warm docs, and bathroom-mirror-grade plain English throughout.

Released under the [MIT License](LICENSE).
