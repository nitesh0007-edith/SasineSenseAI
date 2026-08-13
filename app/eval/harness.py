"""Evaluation harness and baseline comparison report (Phase 11).

Loads gold annotations (JSONL, per ``docs/ANNOTATION_GUIDE.md``), flattens both
gold and predicted extractions to comparable field maps, computes aggregate
metrics, and renders a CSV + Markdown baseline-comparison report.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from app.eval.metrics import PRF, field_prf, review_rate, unsupported_extraction_rate
from app.models.schemas import PropertyRecordExtraction


def load_annotations(path: Path | str) -> list[dict]:
    """Read a JSONL annotation file into a list of dicts (one per document)."""
    items: list[dict] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def flatten_annotation(item: dict) -> dict[str, str | None]:
    """Reduce an annotation record to a flat field->value map for scoring."""
    fields = item.get("fields", {})
    flat: dict[str, str | None] = {
        "document_type": item.get("document_type"),
        "document_date": (fields.get("document_date") or {}).get("value"),
    }
    parties = [p.get("name") for p in item.get("parties", []) if p.get("name")]
    places = [p.get("name") for p in item.get("places", []) if p.get("name")]
    flat["parties"] = "|".join(sorted(parties)) if parties else None
    flat["places"] = "|".join(sorted(places)) if places else None
    return flat


def flatten_extraction(extraction: PropertyRecordExtraction) -> dict[str, str | None]:
    """Reduce a PropertyRecordExtraction to the same flat field->value map."""
    parties = sorted(p.name for p in extraction.parties)
    places = sorted(p.name for p in extraction.places)
    date_value = (
        extraction.document_date.normalized_value or extraction.document_date.value
        if extraction.document_date
        else None
    )
    return {
        "document_type": extraction.document_type,
        "document_date": None if date_value is None else str(date_value),
        "parties": "|".join(parties) if parties else None,
        "places": "|".join(places) if places else None,
    }


def evaluate(
    predictions: dict[str, dict[str, str | None]],
    gold: dict[str, dict[str, str | None]],
    *,
    supported_flags: list[bool] | None = None,
    review_flags: list[bool] | None = None,
) -> dict:
    """Aggregate field P/R/F1 across documents plus reliability metrics."""
    tp = fp = fn = 0
    per_doc: dict[str, PRF] = {}
    for doc_id, gold_fields in gold.items():
        pred_fields = predictions.get(doc_id, {})
        prf = field_prf(pred_fields, gold_fields)
        per_doc[doc_id] = prf
        tp += prf.true_positive
        fp += prf.false_positive
        fn += prf.false_negative

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "documents": len(gold),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "unsupported_extraction_rate": unsupported_extraction_rate(supported_flags or []),
        "review_rate": review_rate(review_flags or []),
        "per_document": {k: vars(v) for k, v in per_doc.items()},
    }


def comparison_report(results_by_baseline: dict[str, dict]) -> tuple[str, str]:
    """Render (csv_text, markdown_text) comparing baselines.

    ``results_by_baseline`` maps a baseline name (e.g. "ocr_only", "hybrid") to
    the dict returned by :func:`evaluate`.
    """
    columns = ["baseline", "documents", "precision", "recall", "f1",
               "unsupported_extraction_rate", "review_rate"]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for name, res in results_by_baseline.items():
        writer.writerow([name] + [res.get(c) for c in columns[1:]])
    csv_text = buffer.getvalue()

    md_lines = ["# Baseline comparison", "", "| " + " | ".join(columns) + " |",
                "| " + " | ".join(["---"] * len(columns)) + " |"]
    for name, res in results_by_baseline.items():
        row = [name] + [str(res.get(c)) for c in columns[1:]]
        md_lines.append("| " + " | ".join(row) + " |")
    md_text = "\n".join(md_lines) + "\n"
    return csv_text, md_text


def write_report(
    results_by_baseline: dict[str, dict],
    *,
    csv_path: Path | str,
    md_path: Path | str,
) -> None:
    csv_text, md_text = comparison_report(results_by_baseline)
    Path(csv_path).write_text(csv_text, encoding="utf-8")
    Path(md_path).write_text(md_text, encoding="utf-8")
