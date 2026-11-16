"""Generate a plain-English session summary from conversation history and state changes."""
from kotoba import llm

_EPISODE_SYSTEM = """\
Write an episode summary for a Korean language learner. Use exactly 4 short paragraphs, no headers or bullet points:

Paragraph 1: The story — what happened this episode (1–2 sentences).
Paragraph 2: Relationship — what changed between the player and the character, and the key moment that caused it (1–2 sentences).
Paragraph 3: Up to 3 language slips from this episode with the correct form, like '먹어 → 먹어요 (반말 instead of 해요체)'. Write 'No slips this episode.' if there were none.
Paragraph 4: One hook sentence about what's coming next. Draw on the hook text if provided; otherwise briefly hint at unfinished business.

Write in plain English. Mention actual Korean forms where relevant.\
"""

_SYSTEM = """\
Write a brief session summary for a Korean language learner. Use exactly 3 short paragraphs, no headers or bullet points:

Paragraph 1: What changed in the relationship and why — be specific about moments (1–2 sentences).
Paragraph 2: Up to 3 language slips with the correct Korean form, like '먹어 → 먹어요 (반말 instead of 해요체)'. Write 'No slips this session.' if there were none.
Paragraph 3: One specific thing she will remember about the player (1 sentence). You MUST take this only from the "New facts learned about the player" list provided. Do not invent facts or use anything the character said about herself. Write 'Nothing new to remember.' if that list is empty.

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
        label = "PLAYER" if msg["role"] == "user" else "SEOYEON"
        conv_lines.append(f"{label}: {msg['content']}")

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


def generate_episode_summary(
    episode_title: str,
    beats_passed: list[str],
    beats_failed: list[str],
    milestones: list[str],
    slips: list[str],
    hook_text: str,
    validated_memories: list[str],
    initial_state: dict,
    final_state: dict,
    char_name: str,
) -> str:
    """Return an English episode summary string."""
    closeness_d = final_state["closeness"] - initial_state["closeness"]
    respect_d = final_state["respect"] - initial_state["respect"]

    beats_text = ""
    if beats_passed:
        beats_text += f"Beats passed: {', '.join(beats_passed)}\n"
    if beats_failed:
        beats_text += f"Beats failed/skipped: {', '.join(beats_failed)}\n"
    if milestones:
        beats_text += f"Milestones: {', '.join(milestones)}\n"

    slips_text = (
        "\n".join(f"- {s}" for s in slips[:3]) if slips else "(none)"
    )
    mems_text = (
        "\n".join(f"- {m}" for m in validated_memories) if validated_memories else "(none)"
    )

    user_msg = (
        f"Episode: {episode_title}\n"
        f"Character: {char_name}\n"
        f"{beats_text}"
        f"Relationship: closeness {initial_state['closeness']}→{final_state['closeness']} "
        f"({'+' if closeness_d >= 0 else ''}{closeness_d}), "
        f"respect {initial_state['respect']}→{final_state['respect']} "
        f"({'+' if respect_d >= 0 else ''}{respect_d}), "
        f"offense={final_state['offense']}\n\n"
        f"Slips:\n{slips_text}\n\n"
        f"Facts learned about the player:\n{mems_text}\n\n"
        f"Hook text (what's coming next): {hook_text or '(none)'}"
    )

    messages = [
        {"role": "system", "content": _EPISODE_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    return llm.chat(messages, temperature=0.3)
