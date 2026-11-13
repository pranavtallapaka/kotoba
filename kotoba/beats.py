"""Beat runner: load episodes, track progress, advance beats.

Public API
----------
load_episode(episode_id)         -> dict
get_or_init_progress(id, ep)     -> dict
current_beat(progress, ep)       -> dict | None
pick_variant(beat, state)        -> str | None
should_advance(turns, passed)    -> bool
advance(id, ep, prog, state, passed) -> (progress, on_fail_note | None)
parse_on_fail_deltas(on_fail)    -> dict[str, int]
format_beat_for_character(beat, variant, fail_note) -> str
format_beginner_frames(beat, support_level) -> str | None
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
EPISODES_DIR = ROOT / "episodes"

DEFAULT_MAX_TURNS = 4


# ---------------------------------------------------------------------------
# Episode loading
# ---------------------------------------------------------------------------

def load_episode(episode_id: str) -> dict:
    """Find and load episodes/<id>.yaml or episodes/<char>/<id>.yaml."""
    direct = EPISODES_DIR / f"{episode_id}.yaml"
    if direct.exists():
        return yaml.safe_load(direct.read_text())
    for path in sorted(EPISODES_DIR.rglob(f"{episode_id}.yaml")):
        return yaml.safe_load(path.read_text())
    raise FileNotFoundError(f"Episode '{episode_id}' not found under {EPISODES_DIR}")


def _beat_by_id(episode: dict, beat_id: str) -> dict | None:
    for b in episode.get("beats", []):
        if b["id"] == beat_id:
            return b
    return None


def _beat_index(episode: dict, beat_id: str) -> int:
    for i, b in enumerate(episode.get("beats", [])):
        if b["id"] == beat_id:
            return i
    return -1


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

def get_or_init_progress(episode_id: str, episode: dict) -> dict:
    """Return progress from DB, initialising to the first beat if absent."""
    from kotoba import db
    prog = db.get_progress(episode_id)
    if prog is None:
        beats = episode.get("beats", [])
        first_id = beats[0]["id"] if beats else None
        db.set_progress(episode_id, beat_id=first_id, turns_on_beat=0, status="active")
        prog = db.get_progress(episode_id)
    return prog


def current_beat(progress: dict, episode: dict) -> dict | None:
    """Return the active beat dict, or None if the episode is complete."""
    if progress.get("status") == "complete":
        return None
    return _beat_by_id(episode, progress.get("current_beat", ""))


# ---------------------------------------------------------------------------
# Variant selection
# ---------------------------------------------------------------------------

def pick_variant(beat: dict, state: dict) -> str | None:
    """Pick the first (positive) variant when the relationship is in good
    shape; last (negative) variant otherwise."""
    variants = beat.get("variants")
    if not variants:
        return None
    if state.get("respect", 50) >= 50 and state.get("offense", "none") == "none":
        return variants[0]
    return variants[-1]


# ---------------------------------------------------------------------------
# Advancement
# ---------------------------------------------------------------------------

def should_advance(turns_on_beat: int, beat_passed: bool | None,
                   max_turns: int = DEFAULT_MAX_TURNS) -> bool:
    """True when beat_passed or the turn cap is reached."""
    return beat_passed is True or turns_on_beat >= max_turns


def parse_on_fail_deltas(on_fail: str) -> dict[str, int]:
    """Parse 'covers for you; respect -3' → {'respect': -3}."""
    deltas: dict[str, int] = {}
    for m in re.finditer(r'\b(closeness|respect)\s+([+-]?\d+)', on_fail):
        deltas[m.group(1)] = int(m.group(2))
    return deltas


def advance(
    episode_id: str,
    episode: dict,
    progress: dict,
    state: dict,
    beat_passed: bool | None,
) -> tuple[dict, str | None]:
    """Move to the next beat (or mark complete).

    Returns (new_progress, on_fail_note).  on_fail_note is set when the beat
    had a pass_if but the player didn't pass it; the caller should inject it
    into the next character turn.
    """
    from kotoba import db

    beats_list = episode.get("beats", [])
    idx = _beat_index(episode, progress.get("current_beat", ""))
    beat = beats_list[idx] if 0 <= idx < len(beats_list) else None

    on_fail_note: str | None = None
    if beat and beat.get("pass_if") and beat_passed is not True:
        on_fail_note = beat.get("on_fail")

    next_idx = idx + 1
    if next_idx >= len(beats_list):
        db.set_progress(episode_id, beat_id=progress.get("current_beat"),
                        turns_on_beat=0, status="complete")
    else:
        next_beat = beats_list[next_idx]
        next_variant = pick_variant(next_beat, state)
        db.set_progress(episode_id, beat_id=next_beat["id"],
                        variant=next_variant, turns_on_beat=0, status="active")

    return db.get_progress(episode_id), on_fail_note


def goto_beat(episode_id: str, episode: dict, beat_id: str, state: dict) -> dict:
    """Jump to a specific beat by id."""
    from kotoba import db
    beat = _beat_by_id(episode, beat_id)
    if beat is None:
        raise ValueError(f"Beat '{beat_id}' not found in episode")
    variant = pick_variant(beat, state)
    db.set_progress(episode_id, beat_id=beat_id, variant=variant,
                    turns_on_beat=0, status="active")
    return db.get_progress(episode_id)


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def format_beat_for_character(
    beat: dict,
    variant: str | None = None,
    fail_note: str | None = None,
) -> str:
    """Return a '## Current scene' section to append to the character prompt."""
    lines = ["## Current scene", beat.get("goal", "")]
    if variant:
        lines.append(f"(Your mood/reaction: {variant})")
    if fail_note:
        narrative = fail_note.split(";")[0].strip()
        lines.append(f"(Just happened: {narrative})")
    return "\n".join(lines)


def format_beginner_frames(beat: dict, support_level: int) -> str | None:
    """Return a suggestion block when support_level <= 1, or None."""
    if support_level > 1:
        return None
    frames = beat.get("beginner_frames")
    if not frames:
        return None
    parts = ["[Suggested replies:"]
    for f in frames[:2]:
        parts.append(f"  {f['korean']}  ({f['gloss']})")
    parts.append("]")
    return "\n".join(parts)
