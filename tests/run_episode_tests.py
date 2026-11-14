"""Automated episode path tests (text mode, no audio, always test.db).

Usage:
    python tests/run_episode_tests.py
    python tests/run_episode_tests.py --episode test_dummy
    python tests/run_episode_tests.py --set closeness=70

KOTOBA_TEST=1 is set automatically; judge runs at temperature=0 with seed=42.
Full logs written to tests/episode_results.log.
"""
import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Must be set before importing kotoba modules so judge._TEST_MODE is True.
TEST_DB = ROOT / "test.db"
PLAYER_FIXTURE = ROOT / "tests" / "fixtures" / "player_test.yaml"
os.environ["KOTOBA_DB"] = str(TEST_DB)
os.environ["KOTOBA_TEST"] = "1"
os.environ["KOTOBA_PLAYER_YAML"] = str(PLAYER_FIXTURE)

import yaml  # noqa: E402

from kotoba import beats as beats_mod, db, judge as judge_mod, state as state_mod  # noqa: E402

SCRIPTS_DIR = Path(__file__).parent / "episodes"
LOG_FILE = Path(__file__).parent / "episode_results.log"

# ---------------------------------------------------------------------------
# Logging: everything goes to the log file; stdout gets only the summary.
# ---------------------------------------------------------------------------

_file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter("%(message)s"))

log = logging.getLogger("episode_test")
log.setLevel(logging.DEBUG)
log.addHandler(_file_handler)
log.propagate = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_db() -> None:
    if TEST_DB.exists():
        TEST_DB.unlink()
    db.init_db()


def _sign(delta: int) -> str:
    if delta > 0:
        return "positive"
    if delta < 0:
        return "negative"
    return "zero"


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_path(script: dict, state_overrides: dict[str, str]) -> tuple[bool, str]:
    """Run one path script end to end.  Returns (passed, first_failure_message)."""
    episode_id = script["episode"]
    path_name = script["path_name"]
    max_turns = script.get("max_turns_per_beat", beats_mod.DEFAULT_MAX_TURNS)

    label = f"{episode_id}/{path_name}"
    log.info("\n" + "=" * 60)
    log.info(f"Path: {label}  max_turns_per_beat={max_turns}")
    log.info("=" * 60)

    _reset_db()

    episode = beats_mod.load_episode(episode_id)
    char_id = episode.get("characters", ["seoyeon"])[0]
    CHARS_DIR = ROOT / "characters"
    char = yaml.safe_load((CHARS_DIR / f"{char_id}.yaml").read_text())
    player = db.load_player()

    # Apply state overrides
    if state_overrides:
        db.get_state(char_id)  # ensure row is created
        int_vars = {"closeness", "respect"}
        db.update_state(
            char_id,
            **{k: int(v) for k, v in state_overrides.items() if k in int_vars},
            **{k: v for k, v in state_overrides.items() if k not in int_vars},
        )

    ep_progress = beats_mod.get_or_init_progress(episode_id, episode)
    beat_turns = 0
    history: list[dict] = []
    beats_reached: list[str] = []
    failures: list[str] = []

    def _fail(msg: str) -> None:
        failures.append(msg)
        log.error(f"  FAIL {msg}")

    for i, turn in enumerate(script.get("turns", [])):
        text: str = turn["say"]
        expect: dict = turn.get("expect", {})

        beat = beats_mod.current_beat(ep_progress, episode)
        beat_id = beat["id"] if beat else None

        if beat_id and beat_id not in beats_reached:
            beats_reached.append(beat_id)

        log.info(f"\nTurn {i + 1}: {text!r}  beat={beat_id}")

        # Check 'beat' expectation before the judge runs
        if "beat" in expect and beat_id != expect["beat"]:
            _fail(f"Turn {i + 1}: beat expected={expect['beat']!r} actual={beat_id!r}")

        state_before = db.get_state(char_id)

        result = judge_mod.judge(
            text=text, character=char, state=state_before, history=history, beat=beat
        )

        log.info(
            f"  register={result.register_used}  beat_passed={result.beat_passed}"
            f"  offense={result.offense}  deltas={result.state_deltas}"
        )

        state_mod.apply_turn(result, char_id, player)
        state_after = db.get_state(char_id)

        # Keep history paired (placeholder assistant reply keeps judge context realistic)
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": "..."})

        # --- Per-turn expectation checks ---

        if "register" in expect and result.register_used != expect["register"]:
            _fail(
                f"Turn {i + 1}: register expected={expect['register']!r}"
                f" actual={result.register_used!r}"
            )

        if "beat_passed" in expect and result.beat_passed != expect["beat_passed"]:
            _fail(
                f"Turn {i + 1}: beat_passed expected={expect['beat_passed']}"
                f" actual={result.beat_passed}"
            )

        if "offense" in expect and result.offense != expect["offense"]:
            _fail(
                f"Turn {i + 1}: offense expected={expect['offense']!r}"
                f" actual={result.offense!r}"
            )

        for var in ("respect", "closeness"):
            key = f"{var}_change"
            if key in expect:
                delta = state_after[var] - state_before[var]
                actual_sign = _sign(delta)
                if actual_sign != expect[key]:
                    _fail(
                        f"Turn {i + 1}: {key} expected={expect[key]!r}"
                        f" actual={actual_sign!r} ({delta:+d})"
                    )

        # --- Beat advancement ---
        if beat:
            beat_turns += 1
            if beats_mod.should_advance(beat_turns, result.beat_passed, max_turns):
                ep_progress, on_fail_note = beats_mod.advance(
                    episode_id, episode, ep_progress, state_after, result.beat_passed
                )
                if on_fail_note:
                    deltas = beats_mod.parse_on_fail_deltas(on_fail_note)
                    if deltas:
                        db.update_state(char_id, **deltas)
                beat_turns = 0

                new_beat = beats_mod.current_beat(ep_progress, episode)
                if new_beat:
                    log.info(
                        f"  → beat: {new_beat['id']}"
                        f"  variant={ep_progress.get('variant')}"
                        + (f"  on_fail: {on_fail_note}" if on_fail_note else "")
                    )
                    if "variant" in expect:
                        actual_v = ep_progress.get("variant")
                        if actual_v != expect["variant"]:
                            _fail(
                                f"Turn {i + 1}: variant expected={expect['variant']!r}"
                                f" actual={actual_v!r}"
                            )
                else:
                    log.info("  → episode complete")

    # --- end_expect ---
    end_expect: dict = script.get("end_expect", {})

    # Include the final current_beat (set even after completion)
    final_beat_id = ep_progress.get("current_beat")
    if final_beat_id and final_beat_id not in beats_reached:
        beats_reached.append(final_beat_id)

    is_complete = ep_progress.get("status") == "complete"
    log.info(
        f"\nEnd: beats_reached={beats_reached}"
        f"  complete={is_complete}  final_beat={final_beat_id}"
        f"  variant={ep_progress.get('variant')}"
    )

    if "episode_complete" in end_expect and is_complete != end_expect["episode_complete"]:
        _fail(
            f"end: episode_complete expected={end_expect['episode_complete']}"
            f" actual={is_complete}"
        )

    if "beats_reached" in end_expect:
        expected_set = set(end_expect["beats_reached"])
        actual_set = set(beats_reached)
        if expected_set != actual_set:
            missing = sorted(expected_set - actual_set)
            extra = sorted(actual_set - expected_set)
            parts = []
            if missing:
                parts.append(f"missing={missing}")
            if extra:
                parts.append(f"extra={extra}")
            _fail(f"end: beats_reached {', '.join(parts)}")

    if "final_beat" in end_expect and final_beat_id != end_expect["final_beat"]:
        _fail(
            f"end: final_beat expected={end_expect['final_beat']!r}"
            f" actual={final_beat_id!r}"
        )

    if "variant" in end_expect:
        actual_v = ep_progress.get("variant")
        if actual_v != end_expect["variant"]:
            _fail(
                f"end: variant expected={end_expect['variant']!r}"
                f" actual={actual_v!r}"
            )

    if failures:
        log.info(f"\nFAIL ({len(failures)} check(s))")
        return False, failures[0]
    log.info("\nPASS")
    return True, ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run automated episode path tests")
    parser.add_argument("--episode", metavar="ID", help="only run paths for this episode id")
    parser.add_argument(
        "--set",
        metavar="VAR=VAL",
        action="append",
        dest="overrides",
        default=[],
        help="initial state override, e.g. --set closeness=70 (repeatable)",
    )
    args = parser.parse_args()

    state_overrides: dict[str, str] = {}
    for item in args.overrides:
        if "=" not in item:
            print(f"error: --set expects VAR=VAL, got {item!r}", file=sys.stderr)
            sys.exit(1)
        k, v = item.split("=", 1)
        state_overrides[k.strip()] = v.strip()

    scripts: list[tuple[Path, dict]] = []
    for path in sorted(SCRIPTS_DIR.glob("*.yaml")):
        script = yaml.safe_load(path.read_text())
        if args.episode and script.get("episode") != args.episode:
            continue
        scripts.append((path, script))

    if not scripts:
        target = f" for episode '{args.episode}'" if args.episode else ""
        print(f"No test scripts found{target} in {SCRIPTS_DIR}", file=sys.stderr)
        sys.exit(1)

    passed = failed = 0
    for _, script in scripts:
        label = f"{script.get('episode', '?')}/{script.get('path_name', '?')}"
        ok, first_fail = run_path(script, state_overrides)
        status = "PASS" if ok else f"FAIL: {first_fail}"
        print(f"  {label:<45} {status}")
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed} passed, {failed} failed  (details → {LOG_FILE.relative_to(ROOT)})")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
