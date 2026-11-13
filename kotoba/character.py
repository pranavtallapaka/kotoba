"""Character prompt builder and reply generator.

build_prompt(char_id) -> system prompt string
reply(history, user_text, char_id) -> Korean reply string
"""
import re
from pathlib import Path

import yaml

from kotoba import llm
from kotoba.db import get_memories, get_state, load_player

HERE = Path(__file__).parent
ROOT = HERE.parent
CHARS_DIR = ROOT / "characters"
TEMPLATE = ROOT / "prompts" / "character.md"

_REGISTER_LABELS = {
    "haeyo": "해요체 (polite informal, -아요/어요 endings)",
    "banmal": "반말 (casual plain form)",
    "formal": "하십시오체 (formal, -습니다 endings)",
}

_OFFENSE_LABELS = {
    "none": "none",
    "mild": "mild",
    "serious": "serious",
}


def _memory_matches(fact: str, user_text: str) -> bool:
    """True if any significant token from fact appears in user_text."""
    lower = user_text.lower()
    for token in fact.split():
        t = token.strip(".,!?()[]").lower()
        if len(t) >= 3 and t in lower:
            return True
    for korean in re.findall(r"[가-힣]{2,}", fact):
        if korean in user_text:
            return True
    return False


def _select_memories(memories: list[dict], user_text: str, n: int = 5) -> list[dict]:
    """Return the most recent n memories plus any older ones whose keywords
    appear in user_text, deduplicated and sorted by age."""
    if len(memories) <= n:
        return memories
    recent = memories[-n:]
    older = memories[:-n]
    matched = [m for m in older if _memory_matches(m["fact"], user_text)]
    seen: set[int] = set()
    result = []
    for m in sorted(recent + matched, key=lambda x: x.get("created_at", "")):
        mid = m.get("id", id(m))
        if mid not in seen:
            seen.add(mid)
            result.append(m)
    return result


def _behavior_note(state: dict, repeat_slip: bool = False) -> str:
    parts = []
    if state["respect"] < 40:
        parts.append(
            "Respect is low (below 40). Give shorter, cooler replies and sound slightly more distant."
        )
    offense = state["offense"]
    if offense == "mild":
        parts.append(
            "Mild offense just occurred. Begin your reply with a brief awkward beat — "
            "something like '아… 네.' or '어… 그래요?' — then continue naturally."
        )
    elif offense == "serious":
        parts.append(
            "Serious offense. Be cold and curt. Ask '무슨 뜻이에요?' or similar before "
            "proceeding. Do not act warmly until 한 씨 addresses the issue."
        )
    if repeat_slip:
        parts.append(
            "한 씨 has made repeated address/register slips this session. "
            "Be noticeably cooler: short replies, no exclamation marks, slightly more formal distance."
        )
    if not parts:
        parts.append("Normal. Be warm but professional.")
    return " ".join(parts)


def build_prompt(char_id: str, user_text: str = "", repeat_slip: bool = False) -> str:
    char = yaml.safe_load((CHARS_DIR / f"{char_id}.yaml").read_text())
    state = get_state(char_id)
    all_mems = get_memories(char_id)
    mems = _select_memories(all_mems, user_text)

    memories_text = (
        "\n".join(f"- {m['fact']}" for m in mems) if mems else "(none yet)"
    )

    fills = {
        "name": char["name"],
        "persona": char["persona"].strip(),
        "closeness": str(state["closeness"]),
        "respect": str(state["respect"]),
        "offense": _OFFENSE_LABELS.get(state["offense"], state["offense"]),
        "register_to_player_label": _REGISTER_LABELS.get(
            state["register_to_player"], state["register_to_player"]
        ),
        "register_expected_label": _REGISTER_LABELS.get(
            state["register_expected"], state["register_expected"]
        ),
        "memories": memories_text,
        "behavior_note": _behavior_note(state, repeat_slip=repeat_slip),
    }
    template = TEMPLATE.read_text()
    result = template
    for key, val in fills.items():
        result = result.replace("{" + key + "}", val)
    return result


def reply(
    history: list[dict],
    user_text: str,
    char_id: str,
    subtitle: bool = False,
    repeat_slip: bool = False,
) -> str | tuple[str, str]:
    """Generate a character reply.

    subtitle=True: returns (korean, english) in one LLM call — no extra latency.
    subtitle=False: returns the Korean string (default, backward-compatible).
    """
    system_prompt = build_prompt(char_id, user_text, repeat_slip=repeat_slip)
    if subtitle:
        system_prompt += (
            "\n\nAfter your Korean reply, on a new line write: "
            "EN: <natural English translation of your reply>"
        )
    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": user_text}]
    )
    raw = llm.chat(messages, temperature=0.8)
    if subtitle:
        if "\nEN: " in raw:
            korean, english = raw.split("\nEN: ", 1)
            return korean.strip(), english.strip()
        return raw.strip(), ""
    return raw
