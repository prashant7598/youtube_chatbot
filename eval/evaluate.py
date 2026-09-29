"""Merge evaluation prompts and answers, then run RAGAS on completed records."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.evaluation.ragas_eval import evaluate_records, write_result


def load_records(questions_path: Path, answers_path: Path) -> list[dict]:
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    answers = {row["id"]: row for row in json.loads(answers_path.read_text(encoding="utf-8"))}
    records = []
    for question in questions:
        answer = answers.get(question["id"], {})
        records.append(
            {
                "video_id": question["video_id"],
                "question": question["question"],
                "reference_answer": answer.get("reference_answer", ""),
                "retrieved_contexts": answer.get("retrieved_contexts", []),
                "generated_answer": answer.get("generated_answer", ""),
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=ROOT / "eval/questions.json")
    parser.add_argument("--answers", type=Path, default=ROOT / "eval/answers.json")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    records = load_records(args.questions, args.answers)
    result = evaluate_records(records)
    output = args.output or ROOT / "eval/results" / f"ragas-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    write_result(result, output)
    print(f"Wrote RAGAS results to {output}")


if __name__ == "__main__":
    main()
