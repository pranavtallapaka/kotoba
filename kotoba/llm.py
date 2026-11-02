"""Thin wrapper around Ollama's local HTTP API.

chat()      — free-text reply
chat_json() — structured reply validated against a Pydantic model;
              retries once on validation error, then raises.

Qwen3 8B ships with a "thinking" mode that adds ~14 s per call.
Ollama 0.19.0+ accepts think=False to suppress it; that is the default here.
"""
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

from kotoba.config import MODEL, OLLAMA_URL

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_CHAT_URL = f"{OLLAMA_URL}/api/chat"


def _post(payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        _CHAT_URL,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama unreachable at {_CHAT_URL}: {exc}") from exc


def chat(
    messages: list[dict],
    *,
    temperature: float = 0.7,
    think: bool = False,
    model: str = MODEL,
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
        "options": {"temperature": temperature},
    }
    t0 = time.perf_counter()
    data = _post(payload)
    secs = time.perf_counter() - t0
    reply = data["message"]["content"]
    log.debug("chat  %.2fs  model=%s  think=%s  chars=%d", secs, model, think, len(reply))
    return reply


def chat_json(
    messages: list[dict],
    schema: Type[T],
    *,
    temperature: float = 0.2,
    think: bool = False,
    model: str = MODEL,
) -> T:
    json_schema = schema.model_json_schema()
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
        "format": json_schema,
        "options": {"temperature": temperature},
    }

    def _attempt(extra_messages: list[dict]) -> T:
        p = dict(payload)
        p["messages"] = messages + extra_messages
        t0 = time.perf_counter()
        data = _post(p)
        secs = time.perf_counter() - t0
        raw = data["message"]["content"]
        log.debug(
            "chat_json  %.2fs  model=%s  schema=%s  raw=%s",
            secs, model, schema.__name__, raw[:120],
        )
        return schema.model_validate_json(raw)

    try:
        return _attempt([])
    except (ValidationError, json.JSONDecodeError) as first_err:
        log.warning("chat_json first attempt failed (%s), retrying", first_err)
        retry_msg = {
            "role": "user",
            "content": (
                f"Your previous reply failed validation: {first_err}. "
                f"Reply with valid JSON matching the schema exactly."
            ),
        }
        try:
            return _attempt([retry_msg])
        except (ValidationError, json.JSONDecodeError) as second_err:
            raise second_err from first_err
