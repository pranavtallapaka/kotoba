"""Scripted 10-turn test: feeds preset Korean lines to Seo-yeon and prints transcript.

Usage: python tools/chat_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kotoba import character
from kotoba.db import init_db, start_session, end_session, log_turn

CHAR_ID = "seoyeon"

SCRIPT = [
    "안녕하세요!",
    "저는 한이에요. 오늘부터 마케팅 팀에서 일해요.",
    "선배님은 여기서 얼마나 됐어요?",
    "와, 2년이요? 대단해요!",
    "이 업무가 좀 어려워요. 도와주실 수 있어요?",
    "감사합니다, 선배님.",
    "점심 같이 먹어요?",
    "한국어를 공부하고 있는데 아직 잘 못해요.",
    "선배님 카톡 아이디가 뭐예요?",
    "오늘 정말 감사했어요. 내일 또 봐요!",
]


def main() -> None:
    init_db()
    session_id = start_session(CHAR_ID)

    history: list[dict] = []
    print(f"=== Scripted chat test: {CHAR_ID} ===\n")

    for i, line in enumerate(SCRIPT, 1):
        print(f"[{i:02d}] You : {line}")
        reply = character.reply(history, line, CHAR_ID)
        print(f"[{i:02d}] 서연: {reply}\n")

        history.append({"role": "user", "content": line})
        history.append({"role": "assistant", "content": reply})

        log_turn(
            session_id=session_id,
            user_text_raw=line,
            user_register="",
            reply_text=reply,
            judge_json={},
        )

    end_session(session_id)
    print("=== end ===")


if __name__ == "__main__":
    main()
