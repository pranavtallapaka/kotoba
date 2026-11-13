"""CLI entry point: python -m kotoba.cli <char_id> [--episode <id>] [--voice]

Commands during a session:
  /en              English translation of her last line
  /hint <English>  how to say it in Korean at the register she expects
  /repeat          replay her last line at normal speed
  /slow            replay her last line slower
  /state           her current state
  /why             last judge reason and state deltas
  /beat            current beat id, goal, and turn count (episode mode)
  /next            skip to next beat (episode mode)
  /goto <beat_id>  jump to a specific beat (episode mode)
  /set <var> <val> set a state variable, e.g. /set closeness 70
  /quit            end the session
"""
import os
import queue
import random
import re
import sys
import threading
import time
from pathlib import Path

import yaml

from kotoba import beats as beats_mod
from kotoba import character, judge as judge_module, llm, stt_config, state as state_module, summaries, tts
from kotoba.db import (
    end_session,
    get_state,
    init_db,
    load_player,
    log_turn,
    start_session,
    update_state,
)

ROOT = Path(__file__).parent.parent
CHARS_DIR = ROOT / "characters"

_REPEAT_PROMPTS = [
    "네? 다시 말해 줄래요?",
    "잘 못 들었어요. 다시 한 번 말해 줄래요?",
    "어? 다시요?",
]

_REGISTER_LABELS = {
    "haeyo": "해요체 (polite informal)",
    "banmal": "반말 (casual)",
    "hapsyo": "하십시오체 (formal)",
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


def _get_voice_input(char_name: str) -> tuple[str, dict | None]:
    """Voice mode: record → confirm loop. Returns (accepted_text, stt_meta | None).

    stt_meta keys: transcript, corrected, avg_logprob, no_speech_prob.
    Returns ("", None) if low confidence — caller should loop without judging.
    """
    from kotoba.voice import record_and_transcribe

    result = record_and_transcribe(language="ko")

    if result.quality_warning:
        print(f"[Voice] {result.quality_warning} Please try again.\n")
        return "", None

    if result.low_confidence:
        prompt = random.choice(_REPEAT_PROMPTS)
        print(f"{char_name}: {prompt}\n")
        return "", None

    lp = f"{result.avg_logprob:.2f}" if result.avg_logprob == result.avg_logprob else "?"
    print(f"I heard: {result.text}  (logprob={lp})")

    while True:
        raw = input("[Enter] accept  [r] re-record  [e] edit\n> ").strip()
        if raw == "":
            return result.text, {
                "transcript": result.text, "corrected": False,
                "avg_logprob": result.avg_logprob, "no_speech_prob": result.no_speech_prob,
                "t_stt_ms": result.t_stt_ms,
            }
        if raw == "r":
            return _get_voice_input(char_name)
        if raw == "e":
            corrected = input("Your correction: ").strip()
            if not corrected:
                continue
            return corrected, {
                "transcript": result.text, "corrected": True,
                "avg_logprob": result.avg_logprob, "no_speech_prob": result.no_speech_prob,
                "t_stt_ms": result.t_stt_ms,
            }


def _do_turn(
    user_input: str,
    char_id: str,
    char: dict,
    player: dict,
    history: list[dict],
    session_id: int,
    session_slips: list[str],
    session_memories: list[str],
    stt_meta: dict | None,
    show_subtitle: bool,
    voice_id: str = "",
    debug: bool = False,
    timing_out: list | None = None,
    beat: dict | None = None,
    beat_variant: str | None = None,
    fail_note: str | None = None,
) -> tuple[judge_module.JudgeResult, list[dict], str]:
    """Parallel judge + streaming reply/TTS. Returns (result, events, reply_text)."""
    t0 = time.perf_counter()
    state = get_state(char_id)
    char_name = char.get("name", char_id)

    # repeat_slip: based on slips already accumulated before this turn
    repeat_slip = len(session_slips) >= 1

    # Pre-build character prompt now, before judge may update state
    system_prompt = character.build_prompt(
        char_id, user_input, repeat_slip=repeat_slip, voice=bool(voice_id),
        beat=beat, beat_variant=beat_variant, fail_note=fail_note,
    )

    # --- Thread A: judge — starts only after reply's first sentence is queued for TTS ---
    _judge_result: list = [None]
    _judge_ms: list = [0]
    _events: list = []
    _reply_done = threading.Event()
    _first_sentence_sent = threading.Event()  # set by producer when first TTS sentence queued

    def _run_judge():
        _first_sentence_sent.wait()  # don't compete with the reply LLM call at t=0
        tj = time.perf_counter()
        _judge_result[0] = judge_module.judge(
            text=user_input, character=char, state=state, history=history, beat=beat
        )
        _judge_ms[0] = int((time.perf_counter() - tj) * 1000)
        _events[:] = state_module.apply_turn(_judge_result[0], char_id, player)
        _reply_done.wait()
        session_memories.extend(m.fact for m in _judge_result[0].new_memories if m.about == "user")
        slip_msg = state_module.explain_slip(_judge_result[0], user_input)
        if slip_msg:
            session_slips.append(slip_msg)
            print(f"[Slip] {slip_msg}\n", flush=True)

    judge_thread = threading.Thread(target=_run_judge, daemon=True)
    judge_thread.start()

    # --- Reply + TTS ---
    _reply_parts: list[str] = []
    _reply_ms: list[int] = [0]
    _llm_first_ms: list[int] = [0]   # time until first sentence queued for TTS
    _tts_first_ms: list[int] = [0]   # time until first audio plays

    use_streaming = bool(voice_id)

    if not use_streaming:
        # Non-streaming path: text mode (no voice), batch mode
        if show_subtitle:
            prompt_to_use = character.build_prompt(
                char_id, user_input, repeat_slip=repeat_slip, subtitle=True, voice=bool(voice_id),
                beat=beat, beat_variant=beat_variant, fail_note=fail_note,
            )
        else:
            prompt_to_use = system_prompt
        t_r = time.perf_counter()
        raw = llm.chat(
            [{"role": "system", "content": prompt_to_use}]
            + history
            + [{"role": "user", "content": user_input}],
            temperature=0.8,
        )
        _reply_ms[0] = int((time.perf_counter() - t_r) * 1000)

        if show_subtitle and "\nEN: " in raw:
            reply_text, subtitle_text = raw.split("\nEN: ", 1)
            reply_text = reply_text.strip()
            subtitle_text = subtitle_text.strip()
        else:
            reply_text = raw.strip()
            subtitle_text = ""

        _reply_parts.append(reply_text)
        print(f"{char_name}: {reply_text}")
        if subtitle_text:
            print(f"       ({subtitle_text})")
        print()

        _first_sentence_sent.set()  # no TTS pipeline; unblock judge immediately
        _reply_done.set()

    else:
        # Streaming path: LLM tokens → sentence queue → TTS consumer
        # Subtitle (if on) is translated in a background thread while audio plays.
        sentence_q: queue.SimpleQueue = queue.SimpleQueue()
        _subtitle_thread: list = [None]

        def _producer():
            t_start = time.perf_counter()
            korean_buf = ""
            first_sent = False

            print(f"{char_name}: ", end="", flush=True)
            for token in character.reply_stream(history, user_input, char_id, system_prompt):
                sys.stdout.write(token)
                sys.stdout.flush()
                _reply_parts.append(token)
                korean_buf += token
                while True:
                    m = re.search(r'(.*?[.?!。！？])\s+', korean_buf)
                    if m:
                        sent = m.group(1).strip()
                        if sent:
                            if not first_sent:
                                _llm_first_ms[0] = int((time.perf_counter() - t0) * 1000)
                                first_sent = True
                                _first_sentence_sent.set()  # reply is streaming; start judge now
                            sentence_q.put(sent)
                        korean_buf = korean_buf[m.end():]
                    else:
                        break
            if korean_buf.strip():
                if not first_sent:
                    _llm_first_ms[0] = int((time.perf_counter() - t0) * 1000)
                    _first_sentence_sent.set()
                sentence_q.put(korean_buf.strip())
            print()
            _reply_ms[0] = int((time.perf_counter() - t_start) * 1000)
            sentence_q.put(None)  # sentinel

            if show_subtitle:
                captured = "".join(_reply_parts).strip()
                def _translate():
                    en = _translate_to_english(captured)
                    print(f"       ({en})\n", flush=True)
                t = threading.Thread(target=_translate, daemon=True)
                t.start()
                _subtitle_thread[0] = t

        def _consumer():
            first = True
            while True:
                sent = sentence_q.get()
                if sent is None:
                    break
                wav = tts.synthesize(sent, voice_id)
                if wav:
                    if first:
                        _tts_first_ms[0] = int((time.perf_counter() - t0) * 1000)
                        first = False
                    try:
                        tts.play(wav)
                    finally:
                        os.unlink(wav)

        t_prod = threading.Thread(target=_producer)
        t_cons = threading.Thread(target=_consumer)
        t_prod.start()
        t_cons.start()
        t_prod.join()
        t_cons.join()       # wait for all audio to finish
        if _subtitle_thread[0]:
            _subtitle_thread[0].join()  # subtitle printed before slip
        _reply_done.set()   # reply text done; judge can now print slip

    judge_thread.join()

    reply_text = "".join(_reply_parts).strip()

    # --- Timing line ---
    t_stt_ms = (stt_meta.get("t_stt_ms", 0) or 0) if stt_meta else 0
    if debug:
        print(
            f"[timing] stt={t_stt_ms/1000:.2f}s  judge={_judge_ms[0]/1000:.2f}s  "
            f"reply={_reply_ms[0]/1000:.2f}s  llm1={_llm_first_ms[0]/1000:.2f}s  "
            f"tts1={_tts_first_ms[0]/1000:.2f}s\n"
        )

    # --- Log turn ---
    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": reply_text})

    log_turn(
        session_id=session_id,
        user_text_raw=user_input,
        user_register=_judge_result[0].register_used,
        reply_text=reply_text,
        judge_json=_judge_result[0].model_dump(
            exclude={"validator_register", "validator_confidence", "validator_override"}
        ),
        stt_transcript=stt_meta["transcript"] if stt_meta else None,
        stt_corrected=stt_meta["corrected"] if stt_meta else False,
        stt_avg_logprob=stt_meta["avg_logprob"] if stt_meta else None,
        stt_no_speech_prob=stt_meta["no_speech_prob"] if stt_meta else None,
        t_stt_ms=t_stt_ms,
        t_judge_ms=_judge_ms[0],
        t_reply_ms=_reply_ms[0],
        t_tts_first_ms=_tts_first_ms[0],
    )

    if timing_out is not None:
        timing_out.append({
            "stt": t_stt_ms,
            "judge": _judge_ms[0],
            "reply": _reply_ms[0],
            "llm1": _llm_first_ms[0],
            "tts1": _tts_first_ms[0],
        })

    return _judge_result[0], _events, reply_text


def _run_batch(
    char_id: str,
    audio_dir: Path,
    session_id: int,
    char: dict,
    player: dict,
    initial_state: dict,
) -> None:
    """Batch mode: feed sorted WAVs from audio_dir, auto-accept, print compact summary."""
    from kotoba.voice import transcribe_file

    wav_files = sorted(audio_dir.glob("*.wav"))
    if not wav_files:
        print(f"[No .wav files found in {audio_dir}]")
        end_session(session_id)
        return

    print(f"\n[Batch mode: {len(wav_files)} files from {audio_dir}]\n")
    print(f"{'T':<4}  {'heard':<35}  {'register':<8}  {'match':<5}  resp  close")
    print("-" * 72)

    history: list[dict] = []
    session_slips: list[str] = []
    session_memories: list[str] = []

    for i, wav in enumerate(wav_files, 1):
        print(f"[T{i}] transcribing {wav.name}…", end=" ", flush=True)
        stt = transcribe_file(str(wav), language="ko")
        lp = f"{stt.avg_logprob:.2f}" if stt.avg_logprob == stt.avg_logprob else "?"

        if stt.low_confidence:
            print(f"LOW CONFIDENCE (logprob={lp}), skipped")
            continue

        stt_meta = {
            "transcript": stt.text, "corrected": False,
            "avg_logprob": stt.avg_logprob, "no_speech_prob": stt.no_speech_prob,
            "t_stt_ms": stt.t_stt_ms,
        }

        state_before = get_state(char_id)
        result, events, reply_text = _do_turn(
            user_input=stt.text,
            char_id=char_id,
            char=char,
            player=player,
            history=history,
            session_id=session_id,
            session_slips=session_slips,
            session_memories=session_memories,
            stt_meta=stt_meta,
            show_subtitle=False,
        )
        state_after = get_state(char_id)

        resp_d = state_after["respect"] - state_before["respect"]
        close_d = state_after["closeness"] - state_before["closeness"]
        match_sym = "✓" if result.register_match else "✗"
        heard_short = stt.text[:33] + ("…" if len(stt.text) > 33 else "")
        resp_str = f"{resp_d:+d}" if resp_d else "  0"
        close_str = f"{close_d:+d}" if close_d else "  0"
        print(f"[T{i}]  {heard_short:<35}  {result.register_used:<8}  {match_sym:<5}  {resp_str:<4}  {close_str}")

    state_final = get_state(char_id)
    print("-" * 72)
    print(
        f"Final state: closeness={state_final['closeness']}  "
        f"respect={state_final['respect']}  offense={state_final['offense']}"
    )
    end_session(session_id)
    print("\n[Batch session ended]")


def _run_bench(char_id: str, audio_dir: Path, voice_id: str) -> None:
    """Bench mode: startup warmup + run WAVs with TTS, print only median timings."""
    import statistics
    from kotoba.voice import transcribe_file

    init_db()
    char = yaml.safe_load((CHARS_DIR / f"{char_id}.yaml").read_text())
    char_name = char.get("name", char_id)
    player = load_player()

    t_startup = time.perf_counter()
    print(f"[Bench] Loading models (STT={stt_config._model_key}, TTS={tts._ENGINE})…", flush=True)
    errors: list[str] = []

    def _w_stt():
        try: stt_config.warmup()
        except Exception as e: errors.append(f"stt: {e}")

    def _w_tts():
        try: tts.warmup(voice_id)
        except Exception as e: errors.append(f"tts: {e}")

    def _w_llm():
        try: llm.warmup()
        except Exception as e: errors.append(f"llm: {e}")

    warmup_threads = [threading.Thread(target=f) for f in (_w_stt, _w_tts, _w_llm)]
    for t in warmup_threads: t.start()
    for t in warmup_threads: t.join()

    startup_s = time.perf_counter() - t_startup
    try:
        import resource, sys as _sys
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        ram_mb = rss // (1024 * 1024) if _sys.platform == "darwin" else rss // 1024
        ram_note = f"  RAM={ram_mb} MB"
    except Exception:
        ram_note = ""
    if errors:
        print(f"[Bench] warmup warnings: {'; '.join(errors)}", flush=True)
    print(f"[Bench] ready in {startup_s:.1f}s{ram_note}\n", flush=True)

    wav_files = sorted(audio_dir.glob("*.wav"))
    if not wav_files:
        print(f"[Bench] no .wav files in {audio_dir}")
        return

    session_id = start_session(char_id)
    history: list[dict] = []
    session_slips: list[str] = []
    session_memories: list[str] = []
    all_timings: list[dict] = []

    for i, wav in enumerate(wav_files, 1):
        print(f"\n[T{i}/{len(wav_files)}] {wav.name}", flush=True)
        stt = transcribe_file(str(wav), language="ko")
        if stt.low_confidence:
            print(f"  LOW CONFIDENCE — skipped")
            continue
        print(f"  heard: {stt.text}")
        stt_meta = {
            "transcript": stt.text, "corrected": False,
            "avg_logprob": stt.avg_logprob, "no_speech_prob": stt.no_speech_prob,
            "t_stt_ms": stt.t_stt_ms,
        }
        _do_turn(
            user_input=stt.text, char_id=char_id, char=char, player=player,
            history=history, session_id=session_id,
            session_slips=session_slips, session_memories=session_memories,
            stt_meta=stt_meta, show_subtitle=False,
            voice_id=voice_id, debug=False, timing_out=all_timings,
        )

    end_session(session_id)

    if not all_timings:
        print("[Bench] no turns completed")
        return

    keys = ["stt", "judge", "reply", "llm1", "tts1"]
    vals = {k: [t[k] for t in all_timings if t.get(k)] for k in keys}
    n = len(all_timings)
    print(f"\n[Bench] median over {n} turn(s):")
    parts = []
    for k in keys:
        v = vals[k]
        if v:
            parts.append(f"  {k}={statistics.median(v)/1000:.2f}s")
    print("".join(parts))


def run(
    char_id: str,
    voice: bool = False,
    audio_dir: Path | None = None,
    debug: bool = False,
    episode_id: str | None = None,
) -> None:
    init_db()
    session_id = start_session(char_id, episode_id=episode_id)

    char = yaml.safe_load((CHARS_DIR / f"{char_id}.yaml").read_text())
    char_name = char.get("name", char_id)
    player = load_player()
    support_ko = player.get("support_level_ko", 2)

    initial_state = get_state(char_id)

    # Episode setup
    episode: dict | None = None
    ep_progress: dict | None = None
    beat_turns: int = 0
    ep_fail_note: str | None = None
    if episode_id:
        episode = beats_mod.load_episode(episode_id)
        ep_progress = beats_mod.get_or_init_progress(episode_id, episode)
        beat_turns = ep_progress.get("turns_on_beat", 0)
        print(f"[에피소드: {episode.get('title', episode_id)}]")

    if audio_dir is not None:
        _run_batch(char_id, audio_dir, session_id, char, player, initial_state)
        return

    char_voice_id = char.get("voice_id") or ""

    if voice and char_voice_id:
        t_startup = time.perf_counter()
        print(f"[Startup] Loading models (STT={stt_config._model_key}, TTS={tts._ENGINE})…", flush=True)
        _startup_errors: list[str] = []

        def _w_stt():
            try:
                stt_config.warmup()
            except Exception as e:
                _startup_errors.append(f"stt: {e}")

        def _w_tts():
            try:
                tts.warmup(char_voice_id)
            except Exception as e:
                _startup_errors.append(f"tts: {e}")

        def _w_llm():
            try:
                llm.warmup()
            except Exception as e:
                _startup_errors.append(f"llm: {e}")

        _warmup_threads = [threading.Thread(target=f) for f in (_w_stt, _w_tts, _w_llm)]
        for t in _warmup_threads:
            t.start()
        for t in _warmup_threads:
            t.join()

        startup_s = time.perf_counter() - t_startup

        try:
            import resource, sys as _sys
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            ram_mb = rss // (1024 * 1024) if _sys.platform == "darwin" else rss // 1024
            ram_note = f"  RAM={ram_mb} MB"
        except Exception:
            ram_note = ""

        if _startup_errors:
            print(f"[Startup] warnings: {'; '.join(_startup_errors)}", flush=True)
        print(f"[Startup] ready in {startup_s:.1f}s{ram_note}\n", flush=True)

    history: list[dict] = []
    last_reply: str = ""
    last_judge: judge_module.JudgeResult | None = None
    last_events: list[dict] = []
    session_slips: list[str] = []
    session_memories: list[str] = []
    quit_requested = False
    show_subtitle = voice and support_ko <= 2

    mode_note = " | --voice active" if voice else ""
    if show_subtitle:
        mode_note += " | subtitles on"
    print(f"\n[세션 시작: {char_id}. Type /quit to end.{mode_note}]\n")

    while True:
        stt_meta: dict | None = None

        if voice:
            try:
                raw_prompt = input("[Press Enter to record, or type a command]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if raw_prompt:
                user_input = raw_prompt
            else:
                user_input, stt_meta = _get_voice_input(char_name)
                if not user_input:
                    continue
        else:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

        if not user_input:
            continue

        if user_input == "/quit":
            quit_requested = True
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
            r_to = _REGISTER_LABELS.get(state["register_to_player"], state["register_to_player"])
            r_exp = _REGISTER_LABELS.get(state["register_expected"], state["register_expected"])
            print(
                f"[State]\n"
                f"  closeness : {state['closeness']}/100\n"
                f"  respect   : {state['respect']}/100\n"
                f"  offense   : {state['offense']}\n"
                f"  her register  : {r_to}\n"
                f"  expects from you: {r_exp}\n"
            )
            continue

        if user_input == "/why":
            if last_judge is None:
                print("[No turn yet]\n")
            else:
                print(f"[Why] {last_judge.reason}")
                for ev in last_events:
                    if ev["variable"] in ("closeness", "respect") and ev["delta"] != 0:
                        sign = "+" if ev["delta"] > 0 else ""
                        print(f"  {ev['variable']}: {sign}{ev['delta']}")
                print()
            continue

        if user_input == "/repeat":
            if last_reply:
                tts.speak(last_reply, char_voice_id)
            else:
                print("[No previous reply]\n")
            continue

        if user_input == "/slow":
            if last_reply:
                tts.speak(last_reply, char_voice_id, slow=True)
            else:
                print("[No previous reply]\n")
            continue

        if user_input == "/beat":
            if not episode:
                print("[No episode active]\n")
            elif ep_progress and ep_progress.get("status") == "complete":
                print("[에피소드 완료]\n")
            else:
                beat = beats_mod.current_beat(ep_progress, episode) if ep_progress else None
                if beat:
                    print(f"[Beat] {beat['id']}: {beat['goal'].strip()}")
                    if beat.get("pass_if"):
                        print(f"  pass_if: {beat['pass_if']}")
                    print(f"  turns on this beat: {beat_turns}/{beats_mod.DEFAULT_MAX_TURNS}\n")
                else:
                    print("[No active beat]\n")
            continue

        if user_input == "/next":
            if not episode or not ep_progress:
                print("[No episode active]\n")
            elif ep_progress.get("status") == "complete":
                print("[에피소드 이미 완료]\n")
            else:
                beat = beats_mod.current_beat(ep_progress, episode)
                ep_progress, _ = beats_mod.advance(
                    episode_id, episode, ep_progress, get_state(char_id), beat_passed=None
                )
                beat_turns = 0
                ep_fail_note = None
                new_beat = beats_mod.current_beat(ep_progress, episode)
                if new_beat:
                    print(f"[→ beat: {new_beat['id']}] {new_beat['goal'].strip()}\n")
                else:
                    print("[에피소드 완료]\n")
            continue

        if user_input.startswith("/goto "):
            target_id = user_input[6:].strip()
            if not episode or not ep_progress:
                print("[No episode active]\n")
            else:
                try:
                    ep_progress = beats_mod.goto_beat(
                        episode_id, episode, target_id, get_state(char_id)
                    )
                    beat_turns = 0
                    ep_fail_note = None
                    new_beat = beats_mod.current_beat(ep_progress, episode)
                    if new_beat:
                        print(f"[→ beat: {new_beat['id']}] {new_beat['goal'].strip()}\n")
                except ValueError as e:
                    print(f"[Error] {e}\n")
            continue

        if user_input.startswith("/set "):
            parts = user_input[5:].split()
            if len(parts) != 2:
                print("[Usage: /set <variable> <value>  — e.g. /set closeness 70]\n")
                continue
            var, raw_val = parts
            allowed_str = {"offense"}
            allowed_int = {"closeness", "respect"}
            if var in allowed_int:
                try:
                    update_state(char_id, **{var: int(raw_val)})
                    print(f"[Set] {var} = {raw_val}\n")
                except ValueError:
                    print(f"[Error] {var} expects an integer\n")
            elif var in allowed_str:
                update_state(char_id, **{var: raw_val})
                print(f"[Set] {var} = {raw_val}\n")
            else:
                print(f"[Error] unknown variable '{var}' — use closeness, respect, or offense\n")
            continue

        # --- Resolve current beat before the turn ---
        beat: dict | None = None
        beat_variant: str | None = None
        if episode and ep_progress:
            beat = beats_mod.current_beat(ep_progress, episode)
            beat_variant = ep_progress.get("variant")
            if beat and support_ko <= 1:
                frames = beats_mod.format_beginner_frames(beat, support_ko)
                if frames:
                    print(frames)

        result, events, char_reply = _do_turn(
            user_input=user_input,
            char_id=char_id,
            char=char,
            player=player,
            history=history,
            session_id=session_id,
            session_slips=session_slips,
            session_memories=session_memories,
            stt_meta=stt_meta,
            show_subtitle=show_subtitle,
            voice_id=char_voice_id if voice else "",
            debug=debug,
            beat=beat,
            beat_variant=beat_variant,
            fail_note=ep_fail_note,
        )
        ep_fail_note = None  # consumed this turn
        last_reply = char_reply
        last_judge = result
        last_events = events

        # --- Beat runner: advance if pass_if met or turn cap reached ---
        if episode and ep_progress and beat:
            beat_turns += 1
            if beats_mod.should_advance(beat_turns, result.beat_passed):
                ep_progress, on_fail_note = beats_mod.advance(
                    episode_id, episode, ep_progress, get_state(char_id), result.beat_passed
                )
                # Apply state deltas from on_fail (e.g. "respect -3")
                if on_fail_note:
                    deltas = beats_mod.parse_on_fail_deltas(on_fail_note)
                    if deltas:
                        update_state(char_id, **deltas)
                ep_fail_note = on_fail_note
                beat_turns = 0

                new_beat = beats_mod.current_beat(ep_progress, episode)
                if new_beat:
                    print(f"\n[→ beat: {new_beat['id']}] {new_beat['goal'].strip()}\n")
                else:
                    print("\n[에피소드 완료! 계속 대화하거나 /quit으로 종료하세요.]\n")

    if quit_requested and history:
        print("[Generating session summary…]", flush=True)
        final_state = get_state(char_id)
        summary = summaries.generate(
            history, session_slips, session_memories, initial_state, final_state
        )
        end_session(session_id, summary=summary)
        print(f"\n[Session Summary]\n{summary}\n")
    else:
        end_session(session_id)
    print("\n[세션 종료]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="kotoba conversation CLI")
    parser.add_argument("char_id", help="character id (e.g. seoyeon)")
    parser.add_argument("--episode", metavar="ID", help="episode id to play (e.g. test_dummy)")
    parser.add_argument("--voice", action="store_true", help="push-to-talk voice input")
    parser.add_argument(
        "--audio-dir",
        metavar="DIR",
        help="batch test: feed sorted WAVs from DIR instead of recording",
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        help="SQLite database path (default: kotoba.db)",
    )
    parser.add_argument("--debug", action="store_true", help="print per-turn timing line")
    parser.add_argument(
        "--tts",
        choices=["say", "melo"],
        default=None,
        help="TTS engine: say (default, no model memory) or melo (MeloTTS neural)",
    )
    parser.add_argument(
        "--bench",
        metavar="DIR",
        nargs="?",
        const="tests/voice_samples",
        help="benchmark: startup + run WAVs from DIR (default: tests/voice_samples), print median timings",
    )
    args = parser.parse_args()

    _prod_db = (ROOT / "kotoba.db").resolve()

    if args.tts:
        tts.set_engine(args.tts)

    if args.db:
        resolved_db = Path(args.db).resolve()
        os.environ["KOTOBA_DB"] = str(resolved_db)
    else:
        resolved_db = _prod_db

    if args.bench:
        bench_dir = Path(args.bench)
        if not args.db:
            os.environ["KOTOBA_DB"] = str(ROOT / "kotoba_bench.db")
        char_yaml = yaml.safe_load((CHARS_DIR / f"{args.char_id}.yaml").read_text())
        voice_id = char_yaml.get("voice_id") or ""
        _run_bench(args.char_id, bench_dir, voice_id)
        sys.exit(0)

    if args.audio_dir and resolved_db == _prod_db:
        print(
            "error: --audio-dir must not run against the production database (kotoba.db).\n"
            "Pass a test database: --db tests/kotoba_test.db",
            file=sys.stderr,
        )
        sys.exit(1)

    audio_dir = Path(args.audio_dir) if args.audio_dir else None
    run(
        args.char_id,
        voice=args.voice or audio_dir is not None,
        audio_dir=audio_dir,
        debug=args.debug,
        episode_id=args.episode,
    )
