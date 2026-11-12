"""Apply a JudgeResult to character state and generate player-facing feedback.

apply_turn(result, char_id, player, turn_id) -> list[dict]
explain_slip(result, user_text) -> str | None
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from kotoba import db
from kotoba.validator_ko import find_register_word

if TYPE_CHECKING:
    from kotoba.judge import JudgeResult

_BEGINNER_RESPECT_CAP = -3
_REG_NAMES = {"banmal": "반말", "haeyo": "해요체", "hapsyo": "하십시오체"}


def apply_turn(
    result: JudgeResult,
    char_id: str,
    player: dict,
    turn_id: int | None = None,
) -> list[dict]:
    """Apply judge deltas to state, log events, store memories. Returns event list."""
    state = db.get_state(char_id)
    support_ko = player.get("support_level_ko", 2)
    # relationship_speed is in player.yaml but not yet in the DB schema,
    # so load_player() never returns it. Default 2.0 halves the turns to threshold.
    rel_speed = float(player.get("relationship_speed", 2.0))
    is_beginner = support_ko <= 2

    raw = dict(result.state_deltas)  # already clamped by judge.py's model_validator
    events: list[dict] = []

    grammar_only = (
        bool(result.grammar_errors)
        and not result.offense_ids
        and not result.honorific_errors
        and result.register_match
    )
    has_slip = not result.register_match or bool(result.honorific_errors)

    if is_beginner:
        if grammar_only and raw.get("respect", 0) < 0:
            raw["respect"] = 0
            events.append({
                "variable": "respect", "delta": 0,
                "reason": "beginner tolerance: grammar-only slip, no respect cost",
            })
        elif has_slip and raw.get("respect", 0) < _BEGINNER_RESPECT_CAP:
            raw["respect"] = _BEGINNER_RESPECT_CAP
            events.append({
                "variable": "respect", "delta": 0,
                "reason": f"beginner tolerance: respect loss capped at {_BEGINNER_RESPECT_CAP}",
            })

    # Scale positive closeness by relationship speed, re-clamp to [-3, +3]
    if raw.get("closeness", 0) > 0:
        raw["closeness"] = max(-3, min(3, int(raw["closeness"] * rel_speed)))

    closeness_delta = raw.get("closeness", 0)
    respect_delta = raw.get("respect", 0)
    new_closeness = state["closeness"]
    new_respect = state["respect"]

    if closeness_delta:
        new_closeness = max(0, min(100, state["closeness"] + closeness_delta))
        events.append({
            "variable": "closeness", "delta": closeness_delta, "reason": result.reason,
        })

    if respect_delta:
        new_respect = max(0, min(100, state["respect"] + respect_delta))
        events.append({
            "variable": "respect", "delta": respect_delta, "reason": result.reason,
        })

    old_offense = state["offense"]
    new_offense = result.offense
    if new_offense != old_offense:
        events.append({
            "variable": "offense", "delta": 0,
            "reason": f"{old_offense} → {new_offense}: {result.reason}",
        })

    db.update_state(char_id, closeness=new_closeness, respect=new_respect, offense=new_offense)

    for ev in events:
        db.log_event(turn_id=turn_id, variable=ev["variable"], delta=ev["delta"], reason=ev["reason"])

    for fact in result.new_memories:
        db.add_memory(char_id, fact, source_turn_id=turn_id)

    return events


def explain_slip(result: JudgeResult, user_text: str) -> str | None:
    """Return one English sentence explaining a register or honorific slip, or None."""
    if result.register_match and not result.honorific_errors:
        return None

    if not result.register_match:
        used = result.register_used
        expected = result.register_expected
        used_name = _REG_NAMES.get(used, used)
        expected_name = _REG_NAMES.get(expected, expected)
        word = find_register_word(user_text, used)

        if used == "banmal" and expected == "haeyo" and word:
            return (
                f"You used {used_name} ({word}) with your senior. "
                f"She expected {expected_name}: {word}요."
            )
        if used == "hapsyo" and expected == "haeyo":
            return f"You used {used_name} (too formal). She expected {expected_name}."
        if word:
            return f"You used {used_name} ({word}). She expected {expected_name}."
        return f"You used {used_name}. She expected {expected_name}."

    if result.honorific_errors:
        first = result.honorific_errors[0]
        return f"Honorific slip: {first}. Use honorific forms when talking about superiors."

    return None
