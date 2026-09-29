"""RAGAS evaluation runner for the JSON records produced by ``eval/evaluate.py``."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def evaluate_records(records: list[dict[str, Any]]) -> Any:
    """Evaluate faithfulness, relevancy, context precision, and context recall with RAGAS."""

    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    except ImportError as error:
        raise RuntimeError("Install the optional evaluation dependencies with: pip install -r requirements.txt") from error

    dataset = Dataset.from_list(
        [
            {
                "question": record["question"],
                "answer": record["generated_answer"],
                "contexts": record["retrieved_contexts"],
                "ground_truth": record["reference_answer"],
            }
            for record in records
            if record.get("generated_answer") and record.get("retrieved_contexts") and record.get("reference_answer")
        ]
    )
    if not len(dataset):
        raise ValueError("No complete evaluation rows found. Supply generated_answer, retrieved_contexts, and reference_answer.")
    return evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision, context_recall])


def write_result(result: Any, output_path: Path) -> None:
    """Persist a compact JSON result that can be compared across prompt or retriever changes."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_pandas().to_json(orient="records", indent=2), encoding="utf-8")
