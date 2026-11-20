"""Evaluate the rule-based Japanese register validator on tests/judge_set_ja.csv.

Usage: python tests/eval_validator_ja.py

Prints a short summary (overall accuracy, per-category, miss count).
Full details written to tests/eval_validator_ja_results.csv.
"""
import os
import sys
from pathlib import Path

# Re-exec with the project venv if not already running inside it.
_venv_python = Path(__file__).parent.parent / ".venv" / "bin" / "python"
if _venv_python.exists() and os.path.realpath(sys.executable) != os.path.realpath(str(_venv_python)):
    os.execv(str(_venv_python), [str(_venv_python)] + sys.argv)

import csv

sys.path.insert(0, str(Path(__file__).parent.parent))

from kotoba.validator_ja import classify

CSV_PATH = Path(__file__).parent / "judge_set_ja.csv"
OUT_CSV = Path(__file__).parent / "eval_validator_ja_results.csv"


def _load_csv() -> list[dict]:
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def run() -> int:
    rows = _load_csv()
    total = len(rows)
    results = []

    for row in rows:
        reg, conf, evidence = classify(row["text"])
        correct = reg == row["expected_register"]
        results.append(
            {
                "row": row,
                "predicted": reg,
                "confidence": conf,
                "evidence": evidence,
                "correct": correct,
            }
        )

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "category", "text", "expected_register",
            "predicted_register", "confidence", "evidence", "correct",
        ])
        for r in results:
            row = r["row"]
            writer.writerow([
                row["id"], row["category"], row["text"],
                row["expected_register"],
                r["predicted"], r["confidence"], r["evidence"], r["correct"],
            ])

    correct_total = sum(1 for r in results if r["correct"])
    acc = correct_total / total if total else 0.0

    categories: dict[str, dict] = {}
    for r in results:
        cat = r["row"]["category"]
        categories.setdefault(cat, {"correct": 0, "total": 0})
        categories[cat]["total"] += 1
        if r["correct"]:
            categories[cat]["correct"] += 1

    misses = [r for r in results if not r["correct"]]

    print("=" * 50)
    print(f"VALIDATOR ACCURACY : {acc*100:.1f}%  ({correct_total}/{total})")
    print()
    print("BY CATEGORY:")
    for cat, counts in sorted(categories.items()):
        c, t = counts["correct"], counts["total"]
        print(f"  {cat:<30} {c}/{t}  ({c/t*100:.0f}%)")
    print()
    if misses:
        print("MISSES:")
        for r in misses:
            print(f"  [{r['row']['id']}] {r['row']['text']!r}")
            print(f"       expected={r['row']['expected_register']}  got={r['predicted']}  evidence={r['evidence']!r}")
        print()
    print(f"Details → {OUT_CSV.name}")
    print("=" * 50)
    return correct_total


if __name__ == "__main__":
    run()
