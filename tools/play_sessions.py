"""Play 3 scripted sessions against kotoba.db for Day 11 analysis.
Run from repo root: .venv/bin/python tools/play_sessions.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from kotoba import character, judge as judge_module, state as state_module, summaries
from kotoba import db as kotoba_db

CHAR_ID = "seoyeon"
CHARS_DIR = Path(__file__).parent.parent / "characters"

SESSIONS = [
    # Session A — clean 해요체, personal info, polite throughout
    [
        "안녕하세요! 저는 한이에요. 오늘부터 마케팅 팀에서 일해요.",
        "선배님 덕분에 많이 배우고 있어요.",
        "저는 미국에서 왔어요. 한국어 공부한 지 2년 됐어요.",
        "오늘 점심 뭐 먹을 거예요?",
        "저도 같이 먹어도 돼요?",
    ],
    # Session B — honorific error, banmal slip, then recovery
    [
        "안녕하세요! 오늘도 잘 부탁드려요.",
        "팀장이 아까 뭐라고 했어요?",           # honorific miss: 팀장→팀장님, 했어요→하셨어요
        "알겠어. 고마워.",                       # banmal slip
        "죄송해요. 해요체로 말할게요. 감사해요, 선배님.",
        "다음에 더 잘할게요.",
    ],
    # Session C — hapsyo (stiff), grammar error, honorific error, then clean
    [
        "안녕하십니까. 처음 뵙겠습니다.",        # hapsyo — stiff but no offense
        "저는 어제 갈 거예요.",                  # grammar error (future+past adverb)
        "오 팀장 말 들었어요?",                  # honorific error: 말→말씀, 팀장→팀장님
        "선배님이 도와주셔서 정말 감사해요.",    # clean haeyo + correct honorific
    ],
]

SESSION_LABELS = ["A — clean 해요체", "B — banmal slip + honorific error", "C — hapsyo + grammar + honorific"]


def run_session(turns: list[str], label: str) -> None:
    kotoba_db.init_db()
    char = yaml.safe_load((CHARS_DIR / f"{CHAR_ID}.yaml").read_text())
    player = kotoba_db.load_player()
    session_id = kotoba_db.start_session(CHAR_ID)
    initial_state = kotoba_db.get_state(CHAR_ID)

    history: list[dict] = []
    session_slips: list[str] = []
    session_memories: list[str] = []

    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"{'='*55}\n")

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
        new_state = kotoba_db.get_state(CHAR_ID)
        print(f"서연: {reply}")
        print(f"      [state: cl={new_state['closeness']} re={new_state['respect']} off={new_state['offense']}]")
        print()

        turn_id = kotoba_db.log_turn(
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
    summary = summaries.generate(history, session_slips, session_memories, initial_state, final_state)
    kotoba_db.end_session(session_id, summary=summary)
    print(f"[Summary] {summary}\n")


if __name__ == "__main__":
    for turns, label in zip(SESSIONS, SESSION_LABELS):
        run_session(turns, label)
    print("\nDone — data written to kotoba.db")
