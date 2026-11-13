"""Integration tests — require Ollama running with qwen3:8b loaded."""
import statistics
import time

import pytest
from pydantic import BaseModel

from kotoba.llm import chat, chat_json


class RegisterCheck(BaseModel):
    speech_register: str   # haeyo | banmal | formal
    register_correct: bool
    reason: str


@pytest.mark.integration
def test_korean_chat_reply():
    messages = [
        {"role": "system", "content": "You are 김서연, a Korean 선배 at a startup. Reply in Korean only."},
        {"role": "user",   "content": "안녕하세요, 선배님. 오늘 날씨가 좋네요."},
    ]
    reply = chat(messages)
    assert isinstance(reply, str)
    assert len(reply) > 0
    # Should be Korean text — check for at least one Korean character
    assert any("가" <= ch <= "힣" for ch in reply), f"No Korean in reply: {reply!r}"
    print(f"\nKorean reply: {reply}")


@pytest.mark.integration
def test_chat_json_10_of_10():
    messages = [
        {
            "role": "user",
            "content": (
                "The user said: '선배 오늘 뭐 해?' to their 선배 (senior). "
                "Classify the register (haeyo, banmal, or formal), "
                "whether it is correct given the relationship, and give a short reason."
            ),
        }
    ]

    latencies = []
    results = []
    for i in range(10):
        t0 = time.perf_counter()
        result = chat_json(messages, RegisterCheck)
        latencies.append(time.perf_counter() - t0)
        results.append(result)

    # All 10 must parse without raising
    assert len(results) == 10, f"Only {len(results)}/10 parsed"

    # Sanity-check values are reasonable
    for r in results:
        assert r.speech_register in {"haeyo", "banmal", "formal"}
        assert isinstance(r.register_correct, bool)
        assert len(r.reason) > 0

    median_ms = statistics.median(latencies) * 1000
    min_ms = min(latencies) * 1000
    max_ms = max(latencies) * 1000
    print(f"\nchat_json 10 calls — median {median_ms:.0f}ms  min {min_ms:.0f}ms  max {max_ms:.0f}ms")
    print(f"Sample result: register={results[0].speech_register}  correct={results[0].register_correct}")
    print(f"Reason: {results[0].reason}")
