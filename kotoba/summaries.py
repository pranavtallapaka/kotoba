"""Generate a plain-English session summary from conversation history and state changes."""
from kotoba import llm

_SYSTEM = """\
Write a brief session summary for a Korean language learner. Use exactly 3 short paragraphs, no headers or bullet points:

Paragraph 1: What changed in the relationship and why — be specific about moments (1–2 sentences).
Paragraph 2: Up to 3 language slips with the correct Korean form, like '먹어 → 먹어요 (반말 instead of 해요체)'. Write 'No slips this session.' if there were none.
Paragraph 3: One specific thing she will remember about the player (1 sentence). Write 'Nothing new to remember.' if no personal facts came up.

Write in plain English. Mention actual Korean forms where relevant.\
"""


def generate(
    history: list[dict],
    session_slips: list[str],
    session_memories: list[str],
    initial_state: dict,
    final_state: dict,
) -> str:
    """Return an English session summary string."""
    closeness_d = final_state["closeness"] - initial_state["closeness"]
    respect_d = final_state["respect"] - initial_state["respect"]

    conv_lines = []
    for msg in history[-12:]:
        role = "You" if msg["role"] == "user" else "서연"
        conv_lines.append(f"{role}: {msg['content']}")

    slips_text = (
        "\n".join(f"- {s}" for s in session_slips[:3]) if session_slips else "(none)"
    )
    mems_text = (
        "\n".join(f"- {m}" for m in session_memories) if session_memories else "(none)"
    )

    user_msg = (
        "Conversation:\n" + "\n".join(conv_lines) + "\n\n"
        f"Relationship: closeness {initial_state['closeness']}→{final_state['closeness']} "
        f"({'+' if closeness_d >= 0 else ''}{closeness_d}), "
        f"respect {initial_state['respect']}→{final_state['respect']} "
        f"({'+' if respect_d >= 0 else ''}{respect_d}), "
        f"offense={final_state['offense']}\n\n"
        f"Slips:\n{slips_text}\n\n"
        f"New facts learned about the player:\n{mems_text}"
    )

    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    return llm.chat(messages, temperature=0.3)
