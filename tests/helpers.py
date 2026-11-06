import copy

from usageledger.client import LLMError

FAKE_RESPONSE = {
    "id": "chatcmpl-test-001",
    "object": "chat.completion",
    "created": 1735689600,
    "model": "llama3.1:8b",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hello! How can I help?"},
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 12,
        "completion_tokens": 34,
        "total_tokens": 46,
    },
}


def ok_response(**overrides):
    response = copy.deepcopy(FAKE_RESPONSE)
    for key, value in overrides.items():
        response[key] = value
    return response


class FakeHttp:
    """Stand-in for usageledger.client.http_post_json."""

    def __init__(self, response=None, error=None):
        self.response = response if response is not None else ok_response()
        self.error = error
        self.calls = []

    def __call__(self, url, payload, timeout=None):
        self.calls.append({"url": url, "payload": payload, "timeout": timeout})
        if self.error is not None:
            raise self.error
        return self.response


def sample_entries():
    """A small ledger covering two months and three models."""
    return [
        {
            "ts": "2026-01-05T10:00:00+00:00",
            "kind": "chat",
            "base_url": "http://localhost:11434/v1",
            "model": "llama3.1:8b",
            "ok": True,
            "error": None,
            "latency_ms": 812,
            "prompt_tokens": 100,
            "completion_tokens": 80,
            "total_tokens": 180,
            "request_snapshot": {},
            "response_snapshot": {},
        },
        {
            "ts": "2026-01-20T10:00:00+00:00",
            "kind": "chat",
            "base_url": "http://localhost:11434/v1",
            "model": "llama3.1:8b",
            "ok": False,
            "error": "server restarted",
            "latency_ms": 42,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "request_snapshot": {},
            "response_snapshot": None,
        },
        {
            "ts": "2026-02-02T10:00:00+00:00",
            "kind": "chat",
            "base_url": "http://localhost:11434/v1",
            "model": "qwen2.5:7b",
            "ok": True,
            "error": None,
            "latency_ms": 1200,
            "prompt_tokens": 50,
            "completion_tokens": 70,
            "total_tokens": 120,
            "request_snapshot": {},
            "response_snapshot": {},
        },
    ]
