"""Tests for the endpoint client: parsing, error paths, and the no-key promise."""

import io
import json
import urllib.error
import urllib.request

import pytest

from usageledger import client
from tests.helpers import FakeHttp, ok_response


def _install(monkeypatch, fake=None):
    fake = fake or FakeHttp()
    monkeypatch.setattr(client, "http_post_json", fake)
    return fake


def test_url_and_payload_construction(monkeypatch):
    fake = _install(monkeypatch)
    client.chat_completions(
        "http://localhost:11434/v1", "llama3.1",
        [{"role": "user", "content": "hi"}],
        max_tokens=8, temperature=0.2,
    )
    assert fake.calls[0]["url"] == "http://localhost:11434/v1/chat/completions"
    payload = fake.calls[0]["payload"]
    assert payload["model"] == "llama3.1"
    assert payload["messages"] == [{"role": "user", "content": "hi"}]
    assert payload["max_tokens"] == 8
    assert payload["temperature"] == 0.2


def test_trailing_slash_base_url(monkeypatch):
    fake = _install(monkeypatch)
    client.chat_completions(
        "http://localhost:11434/v1/", "m", [{"role": "user", "content": "x"}]
    )
    assert fake.calls[0]["url"].endswith("/chat/completions")
    assert "//chat" not in fake.calls[0]["url"]


def test_no_auth_header_ever(monkeypatch):
    """The core promise: never send an API key, even if one is in the env."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-be-sent")
    monkeypatch.setenv("AUTH_TOKEN", "also-never")
    requests_seen = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    response_body = json.dumps(ok_response()).encode()

    def fake_urlopen(request, timeout=None):
        requests_seen.append(request)
        return Response(response_body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client.chat_completions(
        "http://localhost:11434/v1", "m", [{"role": "user", "content": "x"}]
    )

    request = requests_seen[0]
    assert "Authorization" not in (request.headers or {})
    auth_like = {
        k for k in (request.headers or {}) if "auth" in k.lower()
    }
    assert not auth_like
    assert request.get_header("Content-type") == "application/json"


def test_parse_usage_full():
    prompt, completion, total = client.parse_usage(ok_response())
    assert (prompt, completion, total) == (12, 34, 46)


def test_parse_usage_computes_total():
    response = ok_response(usage={"prompt_tokens": 5, "completion_tokens": 7})
    assert client.parse_usage(response) == (5, 7, 12)


def test_parse_usage_missing():
    response = ok_response(usage=None)
    assert client.parse_usage(response) == (None, None, None)


def test_parse_reply():
    assert client.parse_reply(ok_response()) == "Hello! How can I help?"


def test_parse_reply_missing_content():
    response = ok_response(choices=[{"message": {}}])
    with pytest.raises(client.LLMError):
        client.parse_reply(response)


def test_http_error_wrapped_as_llm_error(monkeypatch):
    err = urllib.error.HTTPError(
        "http://x/v1/chat/completions", 500, "boom",
        None, io.BytesIO(b"internal failure"),
    )

    def fake_urlopen(request, timeout=None):
        raise err

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(client.LLMError) as excinfo:
        client.http_post_json("http://x/v1/chat/completions", {})
    assert "HTTP 500" in str(excinfo.value)


def test_url_error_wrapped_as_llm_error(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(client.LLMError) as excinfo:
        client.http_post_json("http://x/v1/chat/completions", {})
    assert "Could not reach" in str(excinfo.value)


def test_non_json_body_wrapped_as_llm_error(monkeypatch):
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout=None):
        return Response(b"<html>not json</html>")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(client.LLMError) as excinfo:
        client.http_post_json("http://x/v1/chat/completions", {})
    assert "non-JSON" in str(excinfo.value)


def test_llm_error_subclasses_runtimeerror():
    assert issubclass(client.LLMError, RuntimeError)
