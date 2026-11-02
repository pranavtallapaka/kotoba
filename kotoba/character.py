"""Character prompt builder and reply generator.

build_prompt(char_id) -> system prompt string
reply(history, user_text, char_id) -> Korean reply string
"""
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
    "mild": "mild (be noticeably cooler and briefer)",
    "serious": "serious (be cold, curt, and clearly uncomfortable)",
}


def build_prompt(char_id: str) -> str:
    char = yaml.safe_load((CHARS_DIR / f"{char_id}.yaml").read_text())
    state = get_state(char_id)
    mems = get_memories(char_id)

    memories_text = (
        "\n".join(f"- {m['fact']}" for m in mems) if mems else "(none yet)"
    )

    template = TEMPLATE.read_text()
    return template.format(
        name=char["name"],
        persona=char["persona"].strip(),
        closeness=state["closeness"],
        respect=state["respect"],
        offense=_OFFENSE_LABELS.get(state["offense"], state["offense"]),
        register_to_player_label=_REGISTER_LABELS.get(
            state["register_to_player"], state["register_to_player"]
        ),
        register_expected_label=_REGISTER_LABELS.get(
            state["register_expected"], state["register_expected"]
        ),
        memories=memories_text,
    )


def reply(history: list[dict], user_text: str, char_id: str) -> str:
    system_prompt = build_prompt(char_id)
    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": user_text}]
    )
    return llm.chat(messages, temperature=0.8)
