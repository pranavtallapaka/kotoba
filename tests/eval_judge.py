"""Evaluate the Korean judge on tests/judge_set_ko.csv.

Usage: python tests/eval_judge.py

Prints a short summary (overall accuracy, per-category, miss count).
Full details written to tests/eval_results.csv.
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
OUT_CSV = Path(__file__).parent / "eval_results.csv"

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
            row["expected_offense_ids"] = [
                x.strip() for x in row["expected_offense_ids"].split(";") if x.strip()
            ]
            rows.append(row)
    return rows


def _precision_recall(predicted: list[str], expected: list[str]) -> tuple[float, float]:
    if not expected and not predicted:
        return 1.0, 1.0
    if not predicted:
        return 1.0, 0.0
    if not expected:
        return 0.0, 1.0
    tp = len(set(predicted) & set(expected))
    return tp / len(predicted), tp / len(expected)


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
                text=row["text"], character=char, state=EVAL_STATE, history=[]
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
            print(f"  [{i:02d}/{total}] {'✓' if reg_correct else '✗'}", end="\r", flush=True)
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
    print()

    # Write full details to CSV
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "category", "text", "expected_register", "predicted_register",
            "reg_correct", "offense_prec", "offense_rec", "validator_override",
            "elapsed_s", "error", "reason",
        ])
        for r in results:
            row = r["row"]
            res = r["result"]
            writer.writerow([
                row["id"], row["category"], row["text"],
                row["expected_register"],
                res.register_used if res else "ERROR",
                r["reg_correct"],
                f"{r['offense_prec']:.2f}", f"{r['offense_rec']:.2f}",
                res.validator_override if res else "",
                f"{r['elapsed']:.1f}",
                r["error"] or "",
                res.reason if res else "",
            ])

    # Summary
    ok = [r for r in results if not r["error"]]
    reg_correct = sum(1 for r in ok if r["reg_correct"])
    reg_acc = reg_correct / total if total else 0.0

    categories: dict[str, dict] = {}
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

    misses = [r for r in results if not r["reg_correct"]]
    errors = [r for r in results if r["error"]]

    print("=" * 50)
    print(f"REGISTER ACCURACY : {reg_acc*100:.1f}%  ({reg_correct}/{total})")
    print()
    print("BY CATEGORY:")
    for cat, counts in sorted(categories.items()):
        c, t = counts["correct"], counts["total"]
        print(f"  {cat:<30} {c}/{t}  ({c/t*100:.0f}%)")
    print()
    print(f"OFFENSE DETECTION : prec {avg_prec*100:.1f}%  rec {avg_rec*100:.1f}%")
    print()
    print(f"MISSES: {len(misses)}  ERRORS: {len(errors)}  (details → {OUT_CSV.name})")
    print("=" * 50)
    return reg_correct


if __name__ == "__main__":
    run()
