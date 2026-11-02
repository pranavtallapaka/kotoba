"""CLI entry point: python -m kotoba.cli <char_id>

Commands during a session:
  /en              English translation of her last line
  /hint <English>  how to say it in Korean at the register she expects
  /state           her current state
  /quit            end the session
"""
import sys

from kotoba import character, llm
from kotoba.db import (
    end_session,
    get_state,
    init_db,
    log_turn,
    start_session,
)

_REGISTER_LABELS = {
    "haeyo": "해요체 (polite informal)",
    "banmal": "반말 (casual)",
    "formal": "하십시오체 (formal)",
}


def _translate_to_english(text: str) -> str:
    msgs = [
        {
            "role": "system",
            "content": (
                "You are a Korean-English translator. "
                "Translate the Korean text to natural English. "
                "Output only the translation, nothing else."
            ),
        },
        {"role": "user", "content": text},
    ]
    return llm.chat(msgs, temperature=0.3)


def _hint_korean(english: str, register: str) -> str:
    register_desc = _REGISTER_LABELS.get(register, register)
    msgs = [
        {
            "role": "system",
            "content": (
                f"You are a Korean language tutor. "
                f"The student wants to say the following in Korean using {register_desc}. "
                f"Respond with only the Korean sentence. "
                f"No explanations, no romanization, no English."
            ),
        },
        {"role": "user", "content": english},
    ]
    return llm.chat(msgs, temperature=0.3)


def run(char_id: str) -> None:
    init_db()
    session_id = start_session(char_id)

    history: list[dict] = []
    last_reply: str = ""

    print(f"\n[세션 시작: {char_id}. Type /quit to end.]\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        if user_input == "/quit":
            break

        if user_input == "/en":
            if last_reply:
                print(f"[EN] {_translate_to_english(last_reply)}\n")
            else:
                print("[No previous reply to translate]\n")
            continue

        if user_input.startswith("/hint "):
            english = user_input[6:].strip()
            if not english:
                print("[Usage: /hint <English phrase>]\n")
                continue
            state = get_state(char_id)
            korean = _hint_korean(english, state["register_expected"])
            print(f"[Hint] {korean}\n")
            continue

        if user_input == "/state":
            state = get_state(char_id)
            r_to = _REGISTER_LABELS.get(
                state["register_to_player"], state["register_to_player"]
            )
            r_exp = _REGISTER_LABELS.get(
                state["register_expected"], state["register_expected"]
            )
            print(
                f"[State]\n"
                f"  closeness : {state['closeness']}/100\n"
                f"  respect   : {state['respect']}/100\n"
                f"  offense   : {state['offense']}\n"
                f"  her register  : {r_to}\n"
                f"  expects from you: {r_exp}\n"
            )
            continue

        # Normal turn — get character reply
        char_reply = character.reply(history, user_input, char_id)
        last_reply = char_reply
        print(f"서연: {char_reply}\n")

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": char_reply})

        log_turn(
            session_id=session_id,
            user_text_raw=user_input,
            user_register="",  # judge will fill this in a later day
            reply_text=char_reply,
            judge_json={},
        )

    end_session(session_id)
    print("\n[세션 종료]")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m kotoba.cli <char_id>")
        sys.exit(1)
    run(sys.argv[1])
