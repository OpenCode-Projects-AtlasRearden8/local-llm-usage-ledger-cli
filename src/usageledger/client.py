"""HTTP client for OpenAI-compatible endpoints.

Deliberately simple: uses only the Python standard library, sends no
Authorization header, and never asks for an API key. Built for local
servers such as Ollama (http://localhost:11434/v1), llama.cpp, LM Studio,
vLLM, or any other OpenAI-compatible endpoint.
"""

import json
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_TIMEOUT = 300
USER_AGENT = "usageledger/0.1.0 (local-llm-usage-ledger-cli)"


class LLMError(RuntimeError):
    """Raised when the endpoint returns an error or an unusable response."""


def chat_completions(base_url, model, messages, *, timeout=DEFAULT_TIMEOUT,
                     max_tokens=None, temperature=None):
    """POST /chat/completions and return the parsed JSON response dict."""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": list(messages)}
    if max_tokens is not None:
        payload["max_tokens"] = int(max_tokens)
    if temperature is not None:
        payload["temperature"] = float(temperature)
    return http_post_json(url, payload, timeout=timeout)


def http_post_json(url, payload, timeout=DEFAULT_TIMEOUT):
    """POST a JSON payload and return the parsed JSON body.

    Kept as a small, separate function so tests can easily mock the
    network layer without hitting a real endpoint.
    """
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:500]
        except Exception:
            pass
        raise LLMError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"Could not reach {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise LLMError(f"Endpoint returned non-JSON from {url}: {exc}") from exc


def parse_usage(response):
    """Extract (prompt, completion, total) token counts from a response."""
    usage = response.get("usage") or {}
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    return prompt, completion, total


def parse_reply(response):
    """Extract the assistant's text reply from a chat completions response."""
    choices = response.get("choices") or []
    for choice in choices:
        message = choice.get("message") or {}
        content = message.get("content")
        if content:
            return content
    raise LLMError("Response contained no assistant message content")
