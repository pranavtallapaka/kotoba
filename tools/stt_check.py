#!/usr/bin/env python3
"""Milestone 1: does speech-to-text keep your mistakes, or silently fix them?

Usage:
  python stt_check.py record              # record every sentence in sentences.csv
  python stt_check.py record --only ko_05 # re-record one sentence
  python stt_check.py test                # transcribe with Whisper turbo
  python stt_check.py test --models turbo large
  python stt_check.py test --dir recordings_tts  # use a different audio directory

Each result is labeled:
  preserved  - transcript matches what you actually said (mistake kept)  -> good
  CORRECTED  - transcript matches the *correct* form (mistake hidden)    -> dangerous
  other      - misheard some other way (check the diff)
"""
import argparse
import csv
import difflib
import re
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIO_DIR = HERE / "recordings"
SENTENCES = HERE / "sentences.csv"
REPORT = HERE / "stt_report.csv"
SAMPLE_RATE = 16000

MODELS = {
    "turbo": "mlx-community/whisper-large-v3-turbo",
    "large": "mlx-community/whisper-large-v3-mlx",
}

PUNCT = re.compile(r"[\s.,!?;:。、！？「」『』…~〜\"'()（）]")


def load_sentences(only=None):
    with open(SENTENCES, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if only:
        rows = [r for r in rows if r["id"] in set(only)]
    return rows


def normalize(text):
    return PUNCT.sub("", unicodedata.normalize("NFKC", text))


def record(rows, redo, audio_dir):
    import numpy as np
    import sounddevice as sd
    import soundfile as sf

    audio_dir.mkdir(exist_ok=True)
    for row in rows:
        out = audio_dir / f"{row['id']}.wav"
        if out.exists() and not redo:
            print(f"[{row['id']}] already recorded, skipping (use --redo to overwrite)")
            continue
        print(f"\n[{row['id']}] {row['error_type']}: {row['note']}")
        print(f"  Say exactly, mistake included:  {row['spoken_text']}")
        input("  Press Enter to start recording...")
        frames = []

        def callback(indata, _frames, _time, status):
            if status:
                print(status, file=sys.stderr)
            frames.append(indata.copy())

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype="float32", callback=callback):
            input("  Recording... press Enter to stop.")
        if not frames:
            print("  Nothing captured; check microphone permissions.")
            continue
        sf.write(out, np.concatenate(frames), SAMPLE_RATE)
        print(f"  Saved {out.name}")


def transcribe(rows, model_keys, audio_dir):
    import mlx_whisper

    results = []
    for key in model_keys:
        repo = MODELS[key]
        print(f"\n=== {key} ({repo}) ===")
        for row in rows:
            wav = audio_dir / f"{row['id']}.wav"
            if not wav.exists():
                print(f"[{row['id']}] no recording, skipping")
                continue
            t0 = time.perf_counter()
            out = mlx_whisper.transcribe(
                str(wav),
                path_or_hf_repo=repo,
                language=row["lang"],
                temperature=0.0,
                condition_on_previous_text=False,
                verbose=None,
            )
            secs = time.perf_counter() - t0
            heard = out["text"].strip()
            segs = out.get("segments") or []
            avg_logprob = (sum(s["avg_logprob"] for s in segs) / len(segs)
                           if segs else float("nan"))
            no_speech_prob = (sum(s["no_speech_prob"] for s in segs) / len(segs)
                              if segs else float("nan"))
            said, fixed, got = (normalize(row["spoken_text"]),
                                normalize(row["correct_form"]), normalize(heard))
            if got == said:
                status = "preserved"
            elif got == fixed:
                status = "CORRECTED"
            else:
                status = "other"
            similarity = difflib.SequenceMatcher(None, said, got).ratio()
            print(f"[{row['id']}] {status:<9}  said: {row['spoken_text']}")
            if status != "preserved":
                print(f"{'':12}  heard: {heard}")
            print(f"{'':12}  {secs:.1f}s  logprob={avg_logprob:.3f}  no_speech={no_speech_prob:.3f}")
            results.append({
                "model": key, "id": row["id"], "lang": row["lang"],
                "error_type": row["error_type"], "status": status,
                "similarity": f"{similarity:.2f}", "said": row["spoken_text"],
                "heard": heard, "correct_form": row["correct_form"],
                "secs": f"{secs:.2f}",
                "avg_logprob": f"{avg_logprob:.3f}",
                "no_speech_prob": f"{no_speech_prob:.3f}",
            })
    return results


def summarize(results):
    print("\n=== Summary ===")
    for model in sorted({r["model"] for r in results}):
        for lang in ("ko", "ja"):
            subset = [r for r in results
                      if r["model"] == model and r["lang"] == lang
                      and r["error_type"] != "control"]
            if not subset:
                continue
            counts = {s: sum(r["status"] == s for r in subset)
                      for s in ("preserved", "CORRECTED", "other")}
            print(f"{model:<6} {lang}: {counts['preserved']}/{len(subset)} preserved, "
                  f"{counts['CORRECTED']} silently corrected, {counts['other']} other")
            corrected = [r["error_type"] for r in subset if r["status"] == "CORRECTED"]
            if corrected:
                print(f"{'':10}corrected error types: {', '.join(sorted(set(corrected)))}")
    with open(REPORT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"\nFull results written to {REPORT.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record", help="record the test sentences")
    rec.add_argument("--only", nargs="+", help="sentence ids to record")
    rec.add_argument("--redo", action="store_true", help="overwrite existing recordings")
    rec.add_argument("--dir", default=None,
                     help="audio directory relative to tools/ (default: recordings)")
    test = sub.add_parser("test", help="transcribe recordings and score them")
    test.add_argument("--only", nargs="+", help="sentence ids to test")
    test.add_argument("--models", nargs="+", default=["turbo"], choices=list(MODELS))
    test.add_argument("--dir", default=None,
                      help="audio directory relative to tools/ (default: recordings)")
    args = parser.parse_args()

    audio_dir = HERE / args.dir if args.dir else AUDIO_DIR

    rows = load_sentences(getattr(args, "only", None))
    if not rows:
        sys.exit("No matching sentences in sentences.csv")

    if args.cmd == "record":
        record(rows, args.redo or bool(args.only), audio_dir)
    else:
        results = transcribe(rows, args.models, audio_dir)
        if results:
            summarize(results)
        else:
            print("No recordings found; run `python stt_check.py record` first.")


if __name__ == "__main__":
    main()
