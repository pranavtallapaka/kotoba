"""Judge: scores a player turn and returns a JudgeResult.

judge(text, character, state, history, beat=None) -> JudgeResult

The judge never writes dialogue. It runs at low temperature and returns
structured JSON validated by Pydantic. Delta bounds are enforced here in
code after parsing so one turn cannot swing the relationship wildly.
"""
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

from kotoba import llm
from kotoba import validator_ko

HERE = Path(__file__).parent
ROOT = HERE.parent
TEMPLATE = ROOT / "prompts" / "judge_ko.md"

# Per-turn bounds (inclusive). Code enforces these; prompt just hints at them.
_CLOSENESS_MIN, _CLOSENESS_MAX = -3, 3
_RESPECT_MIN, _RESPECT_MAX = -10, 3


# ---------------------------------------------------------------------------
# Pydantic schema
# ---------------------------------------------------------------------------

class GrammarError(BaseModel):
    span: str
    fix: str
    type: str       # tense | particle | vocabulary | word_order | other
    severity: Literal["minor", "major"]


class JudgeResult(BaseModel):
    register_used: Literal["hapsyo", "haeyo", "banmal"]
    register_expected: str
    register_match: bool
    offense_ids: list[str]
    honorific_errors: list[str]
    grammar_errors: list[GrammarError]
    beat_passed: bool | None
    new_memories: list[str]
    state_deltas: dict[str, int]
    offense: Literal["none", "mild", "serious"]
    repair_required: bool
    reason: str

    # Set post-LLM by the rule-based validator; not sent to the model.
    validator_register: Literal["hapsyo", "haeyo", "banmal", "unknown"] | None = None
    validator_confidence: Literal["high", "medium", "low"] | None = None
    validator_override: bool = False

    @model_validator(mode="after")
    def _clamp_deltas(self) -> "JudgeResult":
        d = self.state_deltas
        if "closeness" in d:
            d["closeness"] = max(_CLOSENESS_MIN, min(_CLOSENESS_MAX, d["closeness"]))
        if "respect" in d:
            d["respect"] = max(_RESPECT_MIN, min(_RESPECT_MAX, d["respect"]))
        return self


# ---------------------------------------------------------------------------
# Prompt formatting helpers
# ---------------------------------------------------------------------------

def _register_label(r: str) -> str:
    return {"hapsyo": "하십시오체 (hapsyo)", "haeyo": "해요체 (haeyo)", "banmal": "반말 (banmal)"}.get(r, r)


def _format_character_facts(character: dict) -> str:
    name = character.get("name", "?")
    char_id = character.get("id", "?")
    role = character.get("role", "unknown")
    age_offset = character.get("age_offset", "?")
    offenses = character.get("offenses", [])
    offense_lines = "\n".join(f"  - {o}" for o in offenses) if offenses else "  (none)"
    beginner_tol = character.get("beginner_tolerance", False)

    return (
        f"Character: {name} ({char_id})\n"
        f"Role: {role}, age {age_offset} relative to the player\n"
        f"Group: {character.get('group', 'in')}-group\n"
        f"Language: Korean\n"
        f"Offense IDs to check (only flag these):\n{offense_lines}\n"
        f"Beginner tolerance: {'yes — forgive grammar/particle slips; always judge register strictly' if beginner_tol else 'no'}\n"
        f"Superiors in scene: 오 팀장 (team lead, ranks above both player and {name})"
    )


def _format_state_facts(state: dict) -> str:
    offer_made = state.get("register_expected") == "banmal"
    return (
        f"closeness: {state['closeness']}/100\n"
        f"respect: {state['respect']}/100\n"
        f"current offense level: {state['offense']}\n"
        f"register character uses with player: {_register_label(state['register_to_player'])}\n"
        f"register_expected: {state['register_expected']}\n"
        f"반말 offer made: {'yes — banmal_before_offer does NOT apply' if offer_made else 'no — flag banmal as banmal_before_offer'}"
    )


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(start of conversation)"
    tail = history[-8:]  # last 4 pairs
    lines = []
    for msg in tail:
        role = "Player" if msg["role"] == "user" else "Character"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def _format_beat(beat: dict | None) -> str:
    if not beat:
        return "(no active beat)"
    goal = beat.get("goal", "")
    pass_if = beat.get("pass_if", "")
    text = f"goal: {goal}"
    if pass_if:
        text += f"\npass_if: {pass_if}"
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def judge(
    text: str,
    character: dict,
    state: dict,
    history: list[dict],
    beat: dict | None = None,
) -> JudgeResult:
    """Score one player turn and return a JudgeResult."""
    fills = {
        "character_facts": _format_character_facts(character),
        "state_facts": _format_state_facts(state),
        "history": _format_history(history),
        "beat_context": _format_beat(beat),
    }
    template = TEMPLATE.read_text()
    system_prompt = template
    for key, val in fills.items():
        system_prompt = system_prompt.replace("{" + key + "}", val)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f'Analyze this player turn: "{text}"'},
    ]
    result = llm.chat_json(messages, JudgeResult, temperature=0.1, num_predict=400)

    val_reg, val_conf, _ = validator_ko.classify(text)
    result.validator_register = val_reg
    result.validator_confidence = val_conf
    if val_conf == "high" and val_reg != "unknown" and val_reg != result.register_used:
        result.register_used = val_reg
        result.register_match = (val_reg == result.register_expected)
        result.validator_override = True

    # The judge prompt instructs honorific_errors in "X → Y" format.
    # Entries without → are bare address terms the LLM mistakenly flagged
    # (e.g. ['선배님'] when the player used the term correctly).
    result.honorific_errors = [e for e in result.honorific_errors if "→" in e]

    # name_ssi_to_senior: inject offense if player used senior's name + 씨 without a title.
    if "name_ssi_to_senior" in character.get("offenses", []):
        full_name = character.get("name", "")
        given = full_name[-2:] if len(full_name) >= 2 else ""
        if given and re.search(rf"{given}\s*씨", text) and "name_ssi_to_senior" not in result.offense_ids:
            result.offense_ids.append("name_ssi_to_senior")
            if result.offense == "none":
                result.offense = "mild"
            if result.state_deltas.get("respect", 0) >= 0:
                result.state_deltas["respect"] = -2

    # banmal_before_offer requires the player to have actually used banmal.
    # The LLM sometimes fires it on haeyo turns when it sees a medial -어/아 morpheme
    # (e.g. "-어도", "-아서") even though the sentence ends in 요.
    # Strip the false offense and undo the negative respect delta.
    if "banmal_before_offer" in result.offense_ids and result.register_used != "banmal":
        result.offense_ids = [
            oid for oid in result.offense_ids if oid != "banmal_before_offer"
        ]
        if not result.offense_ids and not result.honorific_errors:
            result.offense = "none"
            result.repair_required = False
            if result.state_deltas.get("respect", 0) < 0:
                result.state_deltas["respect"] = 0

    return result
