"""Relationship milestone checker.

check(char_id, char, state, episodes_done) -> list[dict]
  Returns newly triggered milestones and applies their state effects.
"""
from kotoba import db

# State changes to apply when each milestone fires.
_EFFECTS: dict[str, dict] = {
    "drops_ssi":      {"address_form": "name"},
    "she_goes_casual": {"register_to_player": "banmal"},
    "banmal_offer":   {"register_expected": "banmal"},
}


def check(
    char_id: str,
    char: dict,
    state: dict,
    episodes_done: int = 0,
) -> list[dict]:
    """Return newly triggered milestones and persist their effects."""
    milestones = char.get("milestones", [])
    reached = set(state.get("milestones_reached") or [])
    newly_triggered = []

    for m in milestones:
        mid = m["id"]
        if mid in reached:
            continue
        conditions = m.get("conditions", {})
        if "closeness" in conditions and state["closeness"] < conditions["closeness"]:
            continue
        if "respect" in conditions and state["respect"] < conditions["respect"]:
            continue
        if "episodes_done" in conditions and episodes_done < conditions["episodes_done"]:
            continue
        newly_triggered.append(m)
        reached.add(mid)

    if newly_triggered:
        state_updates: dict = {"milestones_reached": list(reached)}
        for m in newly_triggered:
            state_updates.update(_EFFECTS.get(m["id"], {}))
        db.update_state(char_id, **state_updates)

    return newly_triggered
