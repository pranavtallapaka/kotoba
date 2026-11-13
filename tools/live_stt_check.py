"""Live STT accuracy check using the same voice.py path as the app.

Reads tools/sentences.csv (Korean register/honorific rows), records each
sentence through voice.py, and classifies each transcription as:
  preserved — heard matches what was said (error survived)
  CORRECTED — heard matches the correct form (STT silently fixed it)
  other     — something else was transcribed

Writes tests/live_stt_results.csv and prints a one-line summary.

Usage:
    python tools/live_stt_check.py [N]   # N sentences, default 10
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kotoba.voice import record_and_transcribe  # noqa: E402

SENTENCES_CSV = ROOT / "tools" / "sentences.csv"
RESULTS_CSV   = ROOT / "tests" / "live_stt_results.csv"

# 10 sentences: mix of register errors, honorific errors, and controls.
# Covers both boss/teacher scenarios and the 선배 scenario used in the app.
_SELECTED_IDS = [
    "ko_01",  # register — 반말 to boss
    "ko_02",  # register — 반말 to manager
    "ko_03",  # honorific — missing -시- for teacher
    "ko_04",  # honorific — no honorific vocab for grandma
    "ko_11",  # register — 반말 to 선배
    "ko_12",  # honorific — 있어요 instead of 계세요
    "ko_13",  # honorific — missing -시- for 선배's action
    "ko_14",  # register — dropped -요
    "ko_21",  # control — correct 존댓말
    "ko_22",  # control — correct 존댓말
]

_ROMANIZATION = {
    "ko_01": "sa-jang-nim i-geo meo-geo",
    "ko_02": "bu-jang-nim nae-il si-gan i-sseo",
    "ko_03": "seon-saeng-nim-i ji-be ga-sseo-yo",
    "ko_04": "hal-meo-ni-ga ba-beul meo-geo-yo",
    "ko_11": "seon-bae o-neul mwo hae",
    "ko_12": "seon-bae ji-geum i-sseo-yo",
    "ko_13": "seon-bae eo-di ga-yo",
    "ko_14": "gam-sa-hae",
    "ko_21": "an-nyeong-ha-se-yo",
    "ko_22": "jal ji-nae-syeo-sseo-yo",
}


def _normalize(text: str) -> str:
    return re.sub(r"[^\w]", "", text).strip()


def _classify(said: str, heard: str, correct: str) -> str:
    h = _normalize(heard)
    if h == _normalize(said):
        return "preserved"
    if h == _normalize(correct):
        return "CORRECTED"
    return "other"


def main(n: int = 10) -> None:
    # Load selected rows
    all_rows: dict[str, dict] = {}
    with open(SENTENCES_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            all_rows[row["id"]] = row

    ids = _SELECTED_IDS[:n]
    missing = [i for i in ids if i not in all_rows]
    if missing:
        print(f"[Error] IDs not found in sentences.csv: {missing}", file=sys.stderr)
        sys.exit(1)

    results = []
    counts = {"preserved": 0, "CORRECTED": 0, "other": 0}

    print(f"\nLive STT check — {len(ids)} sentences")
    print("Say each sentence as written. The error type is shown so you know what to expect.\n")

    for i, row_id in enumerate(ids, 1):
        row = all_rows[row_id]
        said    = row["spoken_text"]
        correct = row["correct_form"]
        etype   = row["error_type"]
        note    = row.get("note", "")

        roman = _ROMANIZATION.get(row_id, "")
        print(f"[{i}/{len(ids)}]  {said}")
        if roman:
            print(f"         {roman}")
        print(f"         type={etype}  ({note})")

        while True:
            result = record_and_transcribe(language="ko")
            if result.quality_warning:
                print(f"[Quality] {result.quality_warning} Try again.\n")
                continue
            break

        heard = result.text
        lp    = f"{result.avg_logprob:.3f}" if result.avg_logprob == result.avg_logprob else "nan"
        label = _classify(said, heard, correct)
        counts[label] += 1

        sym = {"preserved": "✓ preserved", "CORRECTED": "✗ CORRECTED", "other": "? other"}[label]
        print(f"         heard: {heard}  [{sym}]  logprob={lp}\n")

        results.append({
            "id":          row_id,
            "error_type":  etype,
            "said":        said,
            "correct":     correct,
            "heard":       heard,
            "result":      label,
            "avg_logprob": lp,
        })

    RESULTS_CSV.parent.mkdir(exist_ok=True)
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "error_type", "said", "correct", "heard", "result", "avg_logprob"]
        )
        writer.writeheader()
        writer.writerows(results)

    total = sum(counts.values())
    print(
        f"Summary ({total} turns):  "
        f"preserved={counts['preserved']}  "
        f"CORRECTED={counts['CORRECTED']}  "
        f"other={counts['other']}"
    )
    print(f"Results → {RESULTS_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    main(n)
