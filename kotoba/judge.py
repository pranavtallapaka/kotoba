"""Judge: scores a player turn and returns a JudgeResult.

judge(text, character, state, history, beat=None) -> JudgeResult

The judge never writes dialogue. It runs at low temperature and returns
structured JSON validated by Pydantic. Delta bounds are enforced here in
code after parsing so one turn cannot swing the relationship wildly.
"""
import os
import re
from pathlib import Path
from typing import Literal

_TEST_MODE = bool(os.environ.get("KOTOBA_TEST"))

import yaml
from pydantic import BaseModel, model_validator

from kotoba import llm
from kotoba import honorific_ko
from kotoba import validator_ko
from kotoba import validator_ja
from kotoba.config import JUDGE_MODEL

HERE = Path(__file__).parent
ROOT = HERE.parent
TEMPLATE_KO = ROOT / "prompts" / "judge_ko.md"
TEMPLATE_JA = ROOT / "prompts" / "judge_ja.md"

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


class MemoryItem(BaseModel):
    about: str           # "user" or the character's id (e.g. "seoyeon", "team_lead_oh")
    fact: str
    source_quote: str  # exact substring from the turn that reveals this fact


class JudgeResult(BaseModel):
    register_used: Literal["hapsyo", "haeyo", "banmal", "desu_masu", "plain"]
    register_expected: str
    register_match: bool
    offense_ids: list[str]
    honorific_errors: list[str]
    grammar_errors: list[GrammarError]
    content_met: bool | None   # True/False if beat has a content_condition; null otherwise
    content_evidence: str      # exact substring from player turn satisfying the condition; "" if none
    new_memories: list[MemoryItem]
    state_deltas: dict[str, int]
    offense: Literal["none", "mild", "serious"]
    repair_required: bool
    indirectness_score: int | None = None  # 0–2; Japanese indirectness beats only
    reason: str

    # Computed post-LLM; not sent to the model.
    honorific_subject: str = ""
    honorific_subject_is_senior: bool = False
    honorific_verb_ok: bool = True
    beat_passed: bool | None = None
    validator_register: Literal["hapsyo", "haeyo", "banmal", "desu_masu", "plain", "unknown"] | None = None
    validator_confidence: Literal["high", "medium", "low"] | None = None
    validator_override: bool = False
    # Set by judge_repair() on repair turns.
    repair_ok: bool | None = None
    repair_evidence: str = ""

    @classmethod
    def model_json_schema(cls, **kwargs) -> dict:
        _computed = frozenset({
            "beat_passed", "validator_register", "validator_confidence", "validator_override",
            "honorific_subject", "honorific_subject_is_senior", "honorific_verb_ok",
            "repair_ok", "repair_evidence",
        })
        schema = super().model_json_schema(**kwargs)
        props = schema.get("properties", {})
        for f in _computed:
            props.pop(f, None)
        if "required" in schema:
            schema["required"] = [f for f in schema["required"] if f not in _computed]
        return schema

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


def _register_label_ja(r: str) -> str:
    return {"desu_masu": "です/ます (desu_masu)", "plain": "plain form (casual)"}.get(r, r)


def _format_character_facts(character: dict) -> str:
    lang = character.get("language", "ko")
    name = character.get("name", "?")
    char_id = character.get("id", "?")
    role = character.get("role", "unknown")
    age_offset = character.get("age_offset", "?")
    offenses = character.get("offenses", [])
    offense_lines = "\n".join(f"  - {o}" for o in offenses) if offenses else "  (none)"
    beginner_tol = character.get("beginner_tolerance", False)
    tol_str = "yes — forgive grammar/particle slips; always judge register strictly" if beginner_tol else "no"

    if lang == "ja":
        address_terms = character.get("address_terms", [])
        address_str = "/".join(address_terms) if address_terms else "さん form"
        return (
            f"Character: {name} ({char_id})\n"
            f"Role: {role}, age {age_offset} relative to the player\n"
            f"Group: {character.get('group', 'in')}-group\n"
            f"Language: Japanese\n"
            f"Offense IDs to check (only flag these):\n{offense_lines}\n"
            f"Beginner tolerance: {tol_str}\n"
            f"Expected address from player: {address_str} (first name 蓮 only after drops_san milestone)"
        )

    # Korean
    return (
        f"Character: {name} ({char_id})\n"
        f"Role: {role}, age {age_offset} relative to the player\n"
        f"Group: {character.get('group', 'in')}-group\n"
        f"Language: Korean\n"
        f"Offense IDs to check (only flag these):\n{offense_lines}\n"
        f"Beginner tolerance: {tol_str}\n"
        f"Superiors in scene: 오 팀장 (team lead, ranks above both player and {name})"
    )


def _format_state_facts(state: dict, lang: str = "ko") -> str:
    milestones = state.get("milestones_reached", [])
    milestones_str = ", ".join(milestones) if milestones else "none"

    if lang == "ja":
        offer_made = state.get("register_expected") == "plain"
        drops_san = "drops_san" in milestones
        return (
            f"closeness: {state['closeness']}/100\n"
            f"respect: {state['respect']}/100\n"
            f"current offense level: {state['offense']}\n"
            f"register character uses with player: {_register_label_ja(state['register_to_player'])}\n"
            f"register_expected: {state['register_expected']}\n"
            f"milestones_reached: {milestones_str}\n"
            f"drops_san reached: {'yes — first name (蓮) is now acceptable' if drops_san else 'no — player must use 中島さん or similar さん form'}\n"
            f"タメ口 offer made: {'yes — plain_before_offer does NOT apply' if offer_made else 'no — flag plain form as plain_before_offer'}"
        )

    offer_made = state.get("register_expected") == "banmal"
    return (
        f"closeness: {state['closeness']}/100\n"
        f"respect: {state['respect']}/100\n"
        f"current offense level: {state['offense']}\n"
        f"register character uses with player: {_register_label(state['register_to_player'])}\n"
        f"register_expected: {state['register_expected']}\n"
        f"milestones_reached: {milestones_str}\n"
        f"반말 offer made: {'yes — banmal_before_offer does NOT apply' if offer_made else 'no — flag banmal as banmal_before_offer'}"
    )


def _format_history(history: list[dict], char_name: str = "CHARACTER") -> str:
    if not history:
        return "(start of conversation)"
    tail = history[-8:]  # last 4 pairs
    char_label = char_name.upper()
    lines = []
    for msg in tail:
        label = "PLAYER" if msg["role"] == "user" else char_label
        lines.append(f"{label}: {msg['content']}")
    return "\n".join(lines)


def _format_beat(beat: dict | None) -> str:
    if not beat:
        return "(no active beat)"
    goal = beat.get("goal", "")
    text = f"goal: {goal}"
    pass_if = beat.get("pass_if")
    if pass_if:
        content = pass_if.get("content") if isinstance(pass_if, dict) else str(pass_if)
        if content:
            text += f"\ncontent_condition: {content}"
    if beat.get("judge_indirectness"):
        text += "\njudge_indirectness: true"
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
    other_chars: list[dict] | None = None,
) -> JudgeResult:
    """Score one player turn and return a JudgeResult."""
    lang = character.get("language", "ko")
    char_name = character.get("name", "CHARACTER")
    template_path = TEMPLATE_JA if lang == "ja" else TEMPLATE_KO

    fills = {
        "character_facts": _format_character_facts(character),
        "state_facts": _format_state_facts(state, lang=lang),
        "history": _format_history(history, char_name),
        "beat_context": _format_beat(beat),
        "char_about": character.get("id", "character"),
    }
    system_prompt = template_path.read_text()
    for key, val in fills.items():
        system_prompt = system_prompt.replace("{" + key + "}", val)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f'Analyze this player turn: "{text}"'},
    ]
    result = llm.chat_json(
        messages, JudgeResult,
        temperature=0.0 if _TEST_MODE else 0.1,
        num_predict=450, model=JUDGE_MODEL,
        seed=42 if _TEST_MODE else None,
    )

    # Drop user memories whose source_quote doesn't appear verbatim in the player turn.
    result.new_memories = [
        m for m in result.new_memories
        if m.about != "user" or m.source_quote in text
    ]

    # --- Validator override (language-specific) ---
    if lang == "ja":
        val_reg, val_conf, _ = validator_ja.classify(text)
    else:
        val_reg, val_conf, _ = validator_ko.classify(text)
    result.validator_register = val_reg
    result.validator_confidence = val_conf
    if val_conf == "high" and val_reg != "unknown" and val_reg != result.register_used:
        result.register_used = val_reg
        result.register_match = (val_reg == result.register_expected)
        result.validator_override = True

    if lang == "ja":
        # plain_before_offer guard: strip if the player didn't actually use plain form.
        if "plain_before_offer" in result.offense_ids and result.register_used != "plain":
            result.offense_ids = [
                oid for oid in result.offense_ids if oid != "plain_before_offer"
            ]
            if not result.offense_ids:
                result.offense = "none"
                result.repair_required = False
                if result.state_deltas.get("respect", 0) < 0:
                    result.state_deltas["respect"] = 0
    else:
        # Korean: clean up honorific_errors, enforce name-ssi, banmal guards, honorific check.

        result.honorific_errors = [e for e in result.honorific_errors if "→" in e]

        if "name_ssi_to_senior" in character.get("offenses", []):
            full_name = character.get("name", "")
            given = full_name[-2:] if len(full_name) >= 2 else ""
            if given and re.search(rf"{given}\s*씨", text) and "name_ssi_to_senior" not in result.offense_ids:
                result.offense_ids.append("name_ssi_to_senior")
                if result.offense == "none":
                    result.offense = "mild"
                if result.state_deltas.get("respect", 0) >= 0:
                    result.state_deltas["respect"] = -2

        if "banmal_before_offer" in result.offense_ids and result.register_used != "banmal":
            result.offense_ids = [
                oid for oid in result.offense_ids if oid != "banmal_before_offer"
            ]
            if not result.offense_ids and not result.honorific_errors:
                result.offense = "none"
                result.repair_required = False
                if result.state_deltas.get("respect", 0) < 0:
                    result.state_deltas["respect"] = 0

        # banmal → hapsyo-expected senior is always serious, not mild.
        if (
            "banmal_before_offer" in result.offense_ids
            and result.register_used == "banmal"
            and result.register_expected == "hapsyo"
            and result.offense != "serious"
        ):
            result.offense = "serious"
            result.repair_required = True

        extra_seniors: set[str] = set()
        for c in [character] + (other_chars or []):
            if any(k in c.get("role", "") for k in ("lead", "senior", "teacher", "boss", "president")):
                name = c.get("name", "")
                if name:
                    extra_seniors.add(name)
                    if len(name) >= 2:
                        extra_seniors.add(name[-2:])

        hon = honorific_ko.check(text, frozenset(extra_seniors) if extra_seniors else None)
        result.honorific_subject = hon.subject
        result.honorific_subject_is_senior = hon.subject_is_senior
        result.honorific_verb_ok = hon.verb_has_honorific

        if (
            hon.confidence == "high"
            and hon.subject_is_senior
            and not hon.verb_has_honorific
            and "missing_honorifics_about_superiors" in character.get("offenses", [])
            and "missing_honorifics_about_superiors" not in result.offense_ids
        ):
            result.offense_ids.append("missing_honorifics_about_superiors")
            if result.offense == "none":
                result.offense = "mild"
            if result.state_deltas.get("respect", 0) > -4:
                result.state_deltas["respect"] = -4
            if not result.honorific_errors:
                result.honorific_errors.append(f"{hon.subject} → -(으)시- 필요")

    result.beat_passed = _compute_beat_passed(result, beat, text)
    return result


# ---------------------------------------------------------------------------
# Repair judge
# ---------------------------------------------------------------------------

class RepairResult(BaseModel):
    repair_ok: bool
    repair_evidence: str  # exact substring from player's turn; "" if repair_ok false
    reason: str


_REPAIR_SYSTEM = """\
You are a Korean repair judge. A player committed a serious offense and must now repair it.

A VALID repair satisfies AT LEAST ONE of:
1. An apology in 해요체 or 하십시오체: words like 죄송합니다, 죄송해요, 미안합니다, 미안해요, 실례했습니다
2. Rephrasing the offending utterance at the correct register (haeyo or hapsyo), addressing the same situation

INVALID:
- Any 반말 endings in the response → repair_ok = false
- Changing the subject without addressing the offense → repair_ok = false
- Vague fillers (괜찮아요, 아니에요, 네 alone) with no apology → repair_ok = false

Offense: {offense_description}
Expected register: {register_expected}
Character who was offended: {char_name}

Recent conversation:
{history}

Return JSON:
- repair_ok: true if the response is a valid repair, false otherwise
- repair_evidence: exact substring from the player's turn showing the apology or rephrasing; "" if repair_ok is false
- reason: one concise sentence explaining the verdict\
"""


def judge_repair(
    text: str,
    offense_description: str,
    register_expected: str,
    char_name: str,
    history: list[dict],
) -> RepairResult:
    """Check whether a player turn successfully repairs a prior serious offense."""
    tail = history[-4:]
    char_label = char_name.upper() if char_name else "CHARACTER"
    history_lines = [
        ("PLAYER" if m["role"] == "user" else char_label) + ": " + m["content"]
        for m in tail
    ]
    prompt = (
        _REPAIR_SYSTEM
        .replace("{offense_description}", offense_description)
        .replace("{register_expected}", register_expected)
        .replace("{char_name}", char_name)
        .replace("{history}", "\n".join(history_lines) or "(start of conversation)")
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f'Player repair attempt: "{text}"'},
    ]
    return llm.chat_json(
        messages, RepairResult,
        temperature=0.0 if _TEST_MODE else 0.1,
        num_predict=150, model=JUDGE_MODEL,
        seed=42 if _TEST_MODE else None,
    )


# ---------------------------------------------------------------------------
# Deflection guard (used by _compute_beat_passed)
# ---------------------------------------------------------------------------

# Deflection phrases that can never satisfy a factual content_condition.
_DEFLECTION_RE = re.compile(r"모르겠어요|모르겠습니다|몰라요|모르겠는데|모르겠어")


def _compute_beat_passed(result: "JudgeResult", beat: dict | None, text: str) -> bool | None:
    if beat is None:
        return None
    pass_if = beat.get("pass_if")
    if not pass_if:
        return None

    content = pass_if.get("content") if isinstance(pass_if, dict) else str(pass_if)
    if not content:
        return None

    content_met = result.content_met
    # Guard: if LLM claims met but provides no in-text evidence, it's hallucinating.
    if content_met:
        evidence = result.content_evidence or ""
        if not evidence or evidence not in text:
            content_met = False
    # Guard: deflection phrases never satisfy a factual condition regardless of LLM answer.
    if content_met and _DEFLECTION_RE.search(text):
        content_met = False

    if not isinstance(pass_if, dict) or not pass_if.get("require_register_ok"):
        return content_met

    # require_register_ok: player must not be using casual register (banmal or plain).
    register_ok = result.register_used not in ("banmal", "plain")
    return bool(content_met and register_ok)
