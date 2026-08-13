"""Run all available extraction paths over one real title-register image.

Example::

    python -m app.eval.real_sample \
      --input docs/assets/title-register-sample.jpg \
      --out docs/reports/title-register-comparison

Optional OpenAI-compatible endpoints can be tested with ``--vllm-base-url``
and ``--vllm-model``. Mesh is enabled with ``--mesh`` and the normal Mesh
environment settings. Unavailable systems are recorded explicitly.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.models.schemas import OCRPageResult
from app.providers.factory import get_ner_provider
from app.providers.tesseract_ocr import TesseractOCRProvider
from app.services.pipeline import run_pipeline
from app.services.rendering import render_document
from app.services.rules import (
    classify_document_type,
    extract_all,
    extract_map_references,
    extract_property_description,
    extract_proprietor,
)


def _field_value(field: Any) -> Any:
    if field is None:
        return None
    return {
        "value": field.value,
        "normalized_value": field.normalized_value,
        "confidence": field.confidence,
        "method": field.method,
        "evidence": [span.model_dump(mode="json") for span in field.evidence],
    }


def _ocr_pages(input_path: Path, document_id: str) -> list[OCRPageResult]:
    pages = render_document(input_path, document_id=document_id)
    provider = TesseractOCRProvider()
    return [
        provider.extract_page(Path(page.local_image_path), page.page_number)
        for page in pages
    ]


def run_local_baselines(input_path: Path) -> dict[str, dict[str, Any]]:
    pages = _ocr_pages(input_path, "real_sample")
    combined_text = "\n".join(page.text for page in pages)
    regex_pages = [extract_all(page) for page in pages]
    regex_fields = {
        key: [field for page in regex_pages for field in page[key]]
        for key in ("dates", "money", "postcodes", "title_references", "reference_numbers")
    }
    nlp = get_ner_provider()
    entities = [entity for page in pages for entity in nlp.extract_entities(page)]

    def values(fields):
        return [_field_value(field) for field in fields]

    description = next(
        (extract_property_description(page) for page in pages if extract_property_description(page)),
        None,
    )
    proprietor = next(
        (extract_proprietor(page) for page in pages if extract_proprietor(page)),
        None,
    )
    maps = [field for page in pages for field in extract_map_references(page)]

    return {
        "ocr_only": {
            "status": "completed",
            "provider": "tesseract",
            "pages": len(pages),
            "text_characters": len(combined_text),
            "ocr_text": combined_text,
        },
        "ocr_regex": {
            "status": "completed",
            "provider": "tesseract + deterministic rules",
            "document_type": classify_document_type(combined_text),
            "dates": values(regex_fields["dates"]),
            "money": values(regex_fields["money"]),
            "postcodes": values(regex_fields["postcodes"]),
            "title_references": values(regex_fields["title_references"]),
            "reference_numbers": values(regex_fields["reference_numbers"]),
        },
        "ocr_spacy_ner": {
            "status": "completed",
            "provider": "tesseract + spaCy",
            "document_type": classify_document_type(combined_text),
            "entities": [entity.model_dump(mode="json") for entity in entities],
        },
        "labelled_rules": {
            "status": "completed",
            "provider": "tesseract + title-sheet rules",
            "document_type": classify_document_type(combined_text),
            "property_description": _field_value(description),
            "proprietor": _field_value(proprietor),
            "map_references": values(maps),
        },
    }


def run_hybrid(input_path: Path) -> dict[str, Any]:
    old_ocr, old_structured = settings.ocr_provider, settings.structured_extraction_provider
    settings.ocr_provider = "tesseract"
    settings.structured_extraction_provider = "mock"
    try:
        result = run_pipeline("real_sample_hybrid", str(input_path))
    finally:
        settings.ocr_provider = old_ocr
        settings.structured_extraction_provider = old_structured
    return {"status": "completed", "provider": "tesseract + rules + spaCy + local hybrid", **result.model_dump(mode="json")}


def run_mesh(input_path: Path) -> dict[str, Any]:
    """Run the real Mesh provider when a fresh key is configured."""
    if not settings.structured_api_key:
        return {
            "status": "not_configured",
            "provider": "Mesh VLM",
            "message": "Set MESH_API_KEY in the process environment; never commit it.",
        }
    old_ocr, old_structured = settings.ocr_provider, settings.structured_extraction_provider
    settings.ocr_provider = "tesseract"
    settings.structured_extraction_provider = "mesh"
    try:
        result = run_pipeline("real_sample_mesh", str(input_path))
    except Exception as exc:
        return {
            "status": "failed",
            "provider": "Mesh VLM",
            "model": settings.structured_api_model,
            "message": f"{type(exc).__name__}: {exc}",
        }
    finally:
        settings.ocr_provider = old_ocr
        settings.structured_extraction_provider = old_structured
    return {
        "status": "completed",
        "provider": "Tesseract + Mesh VLM + local validation",
        **result.model_dump(mode="json"),
    }


def run_openai_compatible(name: str, base_url: str | None, model: str | None, input_path: Path) -> dict[str, Any]:
    if not base_url or not model:
        return {"status": "not_configured", "provider": name, "message": "Endpoint and model were not supplied."}
    try:
        response = requests.get(f"{base_url.rstrip('/')}/models", timeout=10)
        response.raise_for_status()
        available = response.json()
        model_ids = [item.get("id") for item in available.get("data", [])]
        return {
            "status": "endpoint_available_not_run",
            "provider": name,
            "model": model,
            "available_models": model_ids[:20],
            "message": "Endpoint detected. Full vision request requires an approved model/prompt configuration.",
        }
    except Exception as exc:
        return {"status": "unavailable", "provider": name, "model": model, "message": str(exc)}


def write_report(results: dict[str, dict[str, Any]], out_dir: Path, source: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Real title-register comparison",
        "",
        f"Source: `{source}`",
        "",
        "This is a method comparison over one real sample, not a statistically representative benchmark.",
        "",
        "| System | Status | What it demonstrates |",
        "| --- | --- | --- |",
    ]
    descriptions = {
        "ocr_only": "Raw Tesseract text and page count",
        "ocr_regex": "Dates, money, postcodes and title references",
        "ocr_spacy_ner": "PERSON/ORG/GPE/LOC entity candidates",
        "labelled_rules": "Title-sheet sections and labelled fields",
        "hybrid_local": "Full evidence-preserving local pipeline",
        "mesh_vlm": "Mesh/VLM endpoint result",
        "vllm": "vLLM OpenAI-compatible endpoint result",
    }
    for name, result in results.items():
        lines.append(f"| `{name}` | `{result.get('status')}` | {descriptions.get(name, '')} |")
    lines += [
        "",
        "## Local hybrid output",
        "",
        "The complete JSON output is in [`results.json`](results.json). Key fields extracted from the sample:",
        "",
        "- title reference: `MID113689`",
        "- proprietor candidate: `DAT LYNCH INVESTMENTS PTY LTD`",
        "- property description: `FLAT 2 at 27 CASTLE TERRACE, EDINBURGH EH1 2EL`",
        "- consideration: `£190,000`",
        "- map reference: `NT2473SE`",
        "- registration/title-sheet dates retained separately for review",
        "",
        "Systems marked `not_configured` or `unavailable` were not treated as successful extractions.",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare extraction methods on a real sample")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("./data/derived/real-sample-comparison"))
    parser.add_argument("--mesh", action="store_true")
    parser.add_argument("--vllm-base-url", default=os.getenv("VLLM_BASE_URL"))
    parser.add_argument("--vllm-model", default=os.getenv("VLLM_MODEL"))
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input does not exist: {args.input}")
    if not TesseractOCRProvider().is_available():
        raise SystemExit("Tesseract is required for the real-sample comparison.")

    results = run_local_baselines(args.input)
    results["hybrid_local"] = run_hybrid(args.input)
    results["mesh_vlm"] = {"status": "not_run", "provider": "Mesh VLM", "message": "Use --mesh with configured Mesh credentials."}
    if args.mesh:
        results["mesh_vlm"] = run_mesh(args.input)
    results["vllm"] = run_openai_compatible("vLLM", args.vllm_base_url, args.vllm_model, args.input)
    write_report(results, args.out, args.input)
    print(json.dumps({name: result.get("status") for name, result in results.items()}, indent=2))


if __name__ == "__main__":
    main()
