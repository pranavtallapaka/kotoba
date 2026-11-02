"""Evaluate the Korean judge on tests/judge_set_ko.csv.

Usage: python tests/eval_judge.py

Reports register accuracy, offense precision/recall, per-category accuracy,
and every miss.
"""
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from kotoba.judge import judge, JudgeResult

CHARS_DIR = Path(__file__).parent.parent / "characters"
CSV_PATH = Path(__file__).parent / "judge_set_ko.csv"

# Fixed state for eval: fresh relationship, 반말 not offered.
EVAL_STATE = {
    "closeness": 20,
    "respect": 50,
    "offense": "none",
    "register_to_player": "haeyo",
    "register_expected": "haeyo",
}


def _load_char() -> dict:
    return yaml.safe_load((CHARS_DIR / "seoyeon.yaml").read_text())


def _load_csv() -> list[dict]:
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["expected_offense_ids"] = (
                [x.strip() for x in row["expected_offense_ids"].split(";") if x.strip()]
            )
            rows.append(row)
    return rows


def _precision_recall(predicted: list[str], expected: list[str]) -> tuple[float, float]:
    if not expected and not predicted:
        return 1.0, 1.0
    if not predicted:
        return 1.0, 0.0  # no false positives, all misses
    if not expected:
        return 0.0, 1.0  # all false positives, trivially recall
    pred_set = set(predicted)
    exp_set = set(expected)
    tp = len(pred_set & exp_set)
    prec = tp / len(pred_set)
    rec = tp / len(exp_set)
    return prec, rec


def run() -> int:
    char = _load_char()
    rows = _load_csv()
    total = len(rows)

    results = []
    print(f"Running judge on {total} rows …", flush=True)

    for i, row in enumerate(rows, 1):
        t0 = time.perf_counter()
        try:
            result: JudgeResult = judge(
                text=row["text"],
                character=char,
                state=EVAL_STATE,
                history=[],
            )
            elapsed = time.perf_counter() - t0
            reg_correct = result.register_used == row["expected_register"]
            prec, rec = _precision_recall(
                result.offense_ids, row["expected_offense_ids"]
            )
            results.append(
                {
                    "row": row,
                    "result": result,
                    "reg_correct": reg_correct,
                    "offense_prec": prec,
                    "offense_rec": rec,
                    "elapsed": elapsed,
                    "error": None,
                }
            )
            status = "✓" if reg_correct else "✗"
            print(
                f"  [{i:02d}/{total}] {status} {row['id']:>2} "
                f"reg={result.register_used:<6} ({elapsed:.1f}s)"
            )
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            results.append(
                {
                    "row": row,
                    "result": None,
                    "reg_correct": False,
                    "offense_prec": 0.0,
                    "offense_rec": 0.0,
                    "elapsed": elapsed,
                    "error": str(exc),
                }
            )
            print(f"  [{i:02d}/{total}] ! {row['id']:>2} ERROR: {exc}")

    # -----------------------------------------------------------------------
    # Metrics
    # -----------------------------------------------------------------------
    errors = [r for r in results if r["error"]]
    ok = [r for r in results if not r["error"]]

    reg_correct = sum(1 for r in ok if r["reg_correct"])
    reg_acc = reg_correct / total if total else 0.0

    categories = {}
    for r in ok:
        cat = r["row"]["category"]
        categories.setdefault(cat, {"correct": 0, "total": 0})
        categories[cat]["total"] += 1
        if r["reg_correct"]:
            categories[cat]["correct"] += 1

    precs = [r["offense_prec"] for r in ok]
    recs = [r["offense_rec"] for r in ok]
    avg_prec = sum(precs) / len(precs) if precs else 0.0
    avg_rec = sum(recs) / len(recs) if recs else 0.0

    print()
    print("=" * 60)
    print(f"REGISTER ACCURACY : {reg_acc*100:.1f}%  ({reg_correct}/{total})")
    print()
    print("BY CATEGORY:")
    for cat, counts in sorted(categories.items()):
        c, t = counts["correct"], counts["total"]
        bar = "✓" * c + "✗" * (t - c)
        print(f"  {cat:<28} {c}/{t}  ({c/t*100:.0f}%)  {bar}")
    print()
    print("OFFENSE DETECTION:")
    print(f"  avg precision : {avg_prec*100:.1f}%")
    print(f"  avg recall    : {avg_rec*100:.1f}%")
    print()

    misses = [r for r in results if not r["reg_correct"]]
    if misses:
        print(f"REGISTER MISSES ({len(misses)}):")
        for r in misses:
            row = r["row"]
            res = r["result"]
            pred = res.register_used if res else "ERROR"
            print(
                f"  id={row['id']:>2}  expected={row['expected_register']:<6}  "
                f"predicted={pred:<6}  cat={row['category']}"
            )
            print(f"         text : {row['text']}")
            print(f"         note : {row['notes']}")
            if res:
                print(f"         reason: {res.reason}")
            print()
    else:
        print("REGISTER MISSES: none")

    offense_misses = [
        r for r in ok
        if r["offense_prec"] < 1.0 or r["offense_rec"] < 1.0
    ]
    if offense_misses:
        print(f"OFFENSE MISSES ({len(offense_misses)}):")
        for r in offense_misses:
            row = r["row"]
            res = r["result"]
            print(
                f"  id={row['id']:>2}  expected={row['expected_offense_ids']}  "
                f"predicted={res.offense_ids}  prec={r['offense_prec']:.2f}  rec={r['offense_rec']:.2f}"
            )
            print(f"         text : {row['text']}")
            print()

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for r in errors:
            print(f"  id={r['row']['id']}  {r['error']}")

    print("=" * 60)
    return reg_correct


if __name__ == "__main__":
    run()
