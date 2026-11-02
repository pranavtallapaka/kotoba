"""Quick smoke-test for mlx-whisper STT.

Usage:
    python tools/stt_check.py [--help]
    python tools/stt_check.py --record 5        # record 5 s then transcribe
    python tools/stt_check.py --file audio.wav  # transcribe an existing file
    python tools/stt_check.py --list            # list sentences from sentences.csv
"""

import argparse
import pathlib
import csv
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
SENTENCES_CSV = HERE / "sentences.csv"


def load_sentences():
    if not SENTENCES_CSV.exists():
        print(f"[warn] {SENTENCES_CSV} not found", file=sys.stderr)
        return []
    with open(SENTENCES_CSV, newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f)]


def transcribe(wav_path: str, model: str = "mlx-community/whisper-large-v3-turbo"):
    import mlx_whisper
    result = mlx_whisper.transcribe(wav_path, path_or_hf_repo=model)
    return result["text"].strip()


def record_audio(seconds: int, sample_rate: int = 16000) -> str:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np

    print(f"Recording {seconds}s … speak now")
    audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate,
                   channels=1, dtype="float32")
    sd.wait()
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio, sample_rate)
    print(f"Saved to {tmp.name}")
    return tmp.name


def main():
    parser = argparse.ArgumentParser(description="Test mlx-whisper STT pipeline")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--record", type=int, metavar="SECONDS",
                       help="record N seconds of audio then transcribe")
    group.add_argument("--file", metavar="WAV", help="transcribe an existing WAV file")
    group.add_argument("--list", action="store_true",
                       help="list practice sentences from sentences.csv")
    parser.add_argument("--model", default="mlx-community/whisper-large-v3-turbo",
                        help="HF repo or local path for mlx-whisper model")
    args = parser.parse_args()

    if args.list:
        rows = load_sentences()
        for r in rows:
            print(f"[{r.get('lang','?')}] {r.get('text','')}  — {r.get('note','')}")
        return

    wav = None
    if args.record:
        wav = record_audio(args.record)
    elif args.file:
        wav = args.file
    else:
        parser.print_help()
        return

    print(f"Transcribing with {args.model} …")
    text = transcribe(wav, model=args.model)
    print(f"Result: {text}")


if __name__ == "__main__":
    main()
