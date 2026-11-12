"""Day 10 integration test: memory persistence across two sessions.

Session 1: introduce yourself and mention your hometown (Busan / 부산).
Session 2: a fresh session — verify the memory persists and check whether
           she references it in conversation.

Usage: python tests/test_day10.py
"""
import os
import sys
import tempfile
from pathlib import Path

_DB = tempfile.mktemp(suffix="_day10.db")
os.environ["KOTOBA_DB"] = _DB

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from kotoba import character, judge as judge_module, state as state_module, summaries
from kotoba import db as kotoba_db

CHAR_ID = "seoyeon"
CHARS_DIR = Path(__file__).parent.parent / "characters"


def run_session(turns: list[str], label: str) -> None:
    char = yaml.safe_load((CHARS_DIR / f"{CHAR_ID}.yaml").read_text())
    player = kotoba_db.load_player()
    session_id = kotoba_db.start_session(CHAR_ID)
    initial_state = kotoba_db.get_state(CHAR_ID)

    history: list[dict] = []
    session_slips: list[str] = []
    session_memories: list[str] = []

    print(f"\n{'='*50}")
    print(f" {label}")
    print(f"{'='*50}\n")

    for text in turns:
        state = kotoba_db.get_state(CHAR_ID)
        print(f"You: {text}")

        result = judge_module.judge(text=text, character=char, state=state, history=history)
        state_module.apply_turn(result, CHAR_ID, player)
        session_memories.extend(result.new_memories)

        slip_msg = state_module.explain_slip(result, text)
        if slip_msg:
            session_slips.append(slip_msg)
            print(f"[Slip] {slip_msg}")

        reply = character.reply(history, text, CHAR_ID)
        print(f"서연: {reply}\n")

        kotoba_db.log_turn(
            session_id=session_id,
            user_text_raw=text,
            user_register=result.register_used,
            reply_text=reply,
            judge_json=result.model_dump(
                exclude={"validator_register", "validator_confidence", "validator_override"}
            ),
        )

        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": reply})

    final_state = kotoba_db.get_state(CHAR_ID)
    summary = summaries.generate(
        history, session_slips, session_memories, initial_state, final_state
    )
    kotoba_db.end_session(session_id, summary=summary)

    print(f"[Session Summary]\n{summary}\n")

    mems = kotoba_db.get_memories(CHAR_ID)
    if mems:
        print(f"[Memories in DB ({len(mems)})]")
        for m in mems:
            print(f"  • {m['fact']}")
        print()


def main() -> None:
    kotoba_db.init_db()

    # Session 1: introduce yourself and reveal hometown
    run_session(
        [
            "안녕하세요! 저는 한이에요. 잘 부탁드려요.",
            "저는 부산에서 왔어요. 선배님은요?",
        ],
        "Session 1 — introducing yourself",
    )

    # Assert memory was stored
    mems = kotoba_db.get_memories(CHAR_ID)
    assert mems, "Expected at least one memory after session 1"
    hometown_mem = any(
        "busan" in m["fact"].lower() or "부산" in m["fact"] for m in mems
    )
    if hometown_mem:
        print("✓ Hometown (부산) stored in memories\n")
    else:
        print(f"⚠ No explicit hometown memory found — stored: {[m['fact'] for m in mems]}\n")

    # Session 2: new session, don't repeat the hometown — see if she brings it up
    run_session(
        [
            "안녕하세요! 오늘도 잘 부탁드려요.",
            "오늘 점심 뭐 먹었어요?",
        ],
        "Session 2 — checking memory carry-over",
    )

    mems2 = kotoba_db.get_memories(CHAR_ID)
    print(f"✓ {len(mems2)} total memories available in session 2")
    print("  (Check transcript above: did she reference 부산 or other session-1 details?)")

    os.unlink(_DB)


if __name__ == "__main__":
    main()
