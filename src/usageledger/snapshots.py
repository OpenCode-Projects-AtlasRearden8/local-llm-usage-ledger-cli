"""Snapshots: compact, honest records of what was sent and received."""

SYSTEM_PROMPT_MARKER = "(system prompt omitted; %d characters)"
TRUNCATION_NOTE = "…[truncated]"

SNAPSHOT_CONTENT_LIMIT = 300


def compact_messages(messages, content_limit=SNAPSHOT_CONTENT_LIMIT):
    """Compress a message list to a short snapshot.

    Keeps role names, truncates long content, and summarizes very long
    system prompts. Never stores more than a few hundred characters.
    """
    snapshot = []
    for message in messages:
        role = message.get("role", "?")
        content = message.get("content") or ""
        content = str(content)
        if role == "system" and len(content) > 80:
            shown = SYSTEM_PROMPT_MARKER % len(content)
        elif len(content) > content_limit:
            shown = content[:content_limit] + TRUNCATION_NOTE
        else:
            shown = content
        snapshot.append({"role": role, "content": shown})
    return snapshot


def compact_response(response, content_limit=SNAPSHOT_CONTENT_LIMIT):
    """Compress an OpenAI-compatible response dict to a short snapshot."""
    finish = None
    text = None
    choices = response.get("choices") or []
    if choices:
        choice = choices[0]
        finish = choice.get("finish_reason")
        message = choice.get("message") or {}
        raw = str(message.get("content") or "")
        if len(raw) > content_limit:
            raw = raw[:content_limit] + TRUNCATION_NOTE
        text = raw
    usage = response.get("usage") or {}
    return {
        "reply": text,
        "finish_reason": finish,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "model_reported": response.get("model"),
        "choices_count": len(choices),
    }
