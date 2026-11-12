"""Day 9 integration test: 3 polite turns + 1 반말 turn.

Verifies: respect drops, offense set, slip explanation fires.
Prints transcript and state_events rows.

Usage: python tests/test_day9.py
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

# Fresh DB so test never touches the real one
_DB = tempfile.mktemp(suffix="_day9.db")
os.environ["KOTOBA_DB"] = _DB

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from kotoba import character, state as state_module
from kotoba import judge as judge_module
from kotoba import db as kotoba_db

CHARS_DIR = Path(__file__).parent.parent / "characters"
CHAR_ID = "seoyeon"

TURNS = [
    "안녕하세요! 저는 한이에요. 잘 부탁드려요.",
    "오늘 날씨가 정말 좋아요!",
    "선배님 이거 어떻게 해요?",
    "뭐 먹어?",  # 반말 — should drop respect and set offense
]


def main() -> None:
    kotoba_db.init_db()
    char = yaml.safe_load((CHARS_DIR / f"{CHAR_ID}.yaml").read_text())
    player = kotoba_db.load_player()

    initial_state = kotoba_db.get_state(CHAR_ID)
    initial_respect = initial_state["respect"]
    print(
        f"[Initial state] closeness={initial_state['closeness']} "
        f"respect={initial_state['respect']} offense={initial_state['offense']}\n"
    )

    history: list[dict] = []

    for i, text in enumerate(TURNS, 1):
        state = kotoba_db.get_state(CHAR_ID)
        print(f"--- Turn {i} ---")
        print(f"You: {text}")

        result = judge_module.judge(text=text, character=char, state=state, history=history)
        state_module.apply_turn(result, CHAR_ID, player)

        slip_msg = state_module.explain_slip(result, text)
        if slip_msg:
            print(f"[Slip] {slip_msg}")

        reply = character.reply(history, text, CHAR_ID)
        print(f"서연: {reply}")

        new_state = kotoba_db.get_state(CHAR_ID)
        print(
            f"[State] closeness={new_state['closeness']} "
            f"respect={new_state['respect']} offense={new_state['offense']}"
        )
        print()

        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": reply})

    # Print state_events
    conn = sqlite3.connect(_DB)
    rows = conn.execute(
        "SELECT variable, delta, reason FROM state_events ORDER BY id"
    ).fetchall()
    conn.close()

    print("=== state_events ===")
    for var, delta, reason in rows:
        sign = "+" if delta > 0 else ""
        delta_str = f"{sign}{delta:.0f}" if delta != 0 else "0"
        print(f"  {var:<12} {delta_str:>4}  {reason}")
    print()

    final_state = kotoba_db.get_state(CHAR_ID)
    print(f"[Final state] closeness={final_state['closeness']} respect={final_state['respect']} offense={final_state['offense']}")

    # Assertions
    assert final_state["offense"] in ("mild", "serious"), (
        f"Expected offense after 반말, got: {final_state['offense']}"
    )
    assert final_state["respect"] < initial_respect, (
        f"Expected respect < {initial_respect} after 반말, got: {final_state['respect']}"
    )
    print("\n✓ Respect dropped after 반말 turn")
    print("✓ Offense set to mild/serious")

    os.unlink(_DB)


if __name__ == "__main__":
    main()
