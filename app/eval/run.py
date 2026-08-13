"""Phase 11 baseline comparison runner.

Builds a small synthetic labelled corpus, runs several points on the baseline
ladder (OCR+regex, OCR+mock-VLM, OCR+real-VLM), scores each against gold, and
writes a CSV + Markdown comparison report.

The mock-VLM baseline is deliberately included: it returns a fixed canned answer,
so it scores well on the document it was hand-tuned for and poorly on others —
illustrating exactly why the research question compares against real hybrids.

Run:
    python -m app.eval.run                 # OCR+regex and OCR+mock-VLM (no network)
    MESH_API_KEY=rsk_... python -m app.eval.run --live   # also runs real VLM

TODO: replace the synthetic corpus with a real annotated dataset for a
research-grade comparison (see docs/ANNOTATION_GUIDE.md).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz

from app.core.config import settings
from app.eval.harness import evaluate, flatten_extraction, write_report
from app.providers.tesseract_ocr import TesseractOCRProvider
from app.services.rendering import render_document
from app.services.rules import classify_document_type, extract_all
from app.services.validation import _evidence_supports

# --- synthetic labelled corpus --------------------------------------------
CORPUS = [
    {
        "document_id": "syneval_001",
        "text": (
            "DISPOSITION\n\nI, John Campbell, residing at 5 High Street, Glasgow, in\n"
            "favour of Mary Fraser, hereby dispone the lands of Craigmillar, dated\n"
            "12 May 1876, for the sum of £1,250 sterling. Title number GLA123456."
        ),
        "gold": {
            "document_type": "disposition",
            "document_date": "1876-05-12",
            "parties": "John Campbell|Mary Fraser",
            "places": "Glasgow",
        },
    },
    {
        "document_id": "syneval_002",
        "text": (
            "FEU CHARTER\n\nArchibald Stewart, in favour of Helen Munro, of the lands\n"
            "of Balornock situated in Aberdeen, dated 3 March 1902, title ABD654321."
        ),
        "gold": {
            "document_type": "deed",
            "document_date": "1902-03-03",
            "parties": "Archibald Stewart|Helen Munro",
            "places": "Aberdeen",
        },
    },
]


def build_corpus(base_dir: Path) -> tuple[list[tuple[str, Path]], dict[str, dict]]:
    base_dir.mkdir(parents=True, exist_ok=True)
    docs: list[tuple[str, Path]] = []
    gold: dict[str, dict] = {}
    for item in CORPUS:
        pdf_path = base_dir / f"{item['document_id']}.pdf"
        doc = fitz.open()
        page = doc.new_page(width=470, height=300)
        page.insert_text((20, 30), item["text"], fontsize=11)
        doc.save(pdf_path)
        doc.close()
        docs.append((item["document_id"], pdf_path))
        gold[item["document_id"]] = item["gold"]
    return docs, gold


# --- baselines -------------------------------------------------------------
def predict_ocr_regex(document_id: str, pdf_path: Path) -> tuple[dict, list[bool], bool]:
    """OCR + deterministic regex only (no NER, no VLM)."""
    pages = render_document(pdf_path, document_id=document_id, dpi=200)
    images = [Path(p.local_image_path) for p in pages]
    ocr = TesseractOCRProvider()
    ocr_pages = [ocr.extract_page(images[0], 1)]
    text = "\n".join(p.text for p in ocr_pages)

    fields = extract_all(ocr_pages[0])
    dates = fields["dates"]
    date_value = None
    supported: list[bool] = []
    if dates:
        best = max(dates, key=lambda f: f.confidence)
        date_value = best.normalized_value or best.value
        supported.append(_evidence_supports(best))

    prediction = {
        "document_type": classify_document_type(text),
        "document_date": date_value,
        "parties": None,  # regex baseline extracts no parties
        "places": None,   # or places
    }
    return prediction, supported, True  # regex baseline always needs review


def predict_pipeline(
    document_id: str, pdf_path: Path, *, ocr: str, structured: str
) -> tuple[dict, list[bool], bool]:
    """Full hybrid pipeline with the chosen OCR + structured providers."""
    from app.services.pipeline import run_pipeline

    old_ocr, old_struct = settings.ocr_provider, settings.structured_extraction_provider
    settings.ocr_provider = ocr
    settings.structured_extraction_provider = structured
    try:
        result = run_pipeline(document_id, str(pdf_path))
    finally:
        settings.ocr_provider = old_ocr
        settings.structured_extraction_provider = old_struct

    supported: list[bool] = []
    if result.document_date is not None:
        supported.append(_evidence_supports(result.document_date))
    for place in result.places:
        supported.append(bool(place.evidence))
    return flatten_extraction(result), supported, result.review_required


def run_comparison(base_dir: Path, *, include_mesh: bool) -> dict[str, dict]:
    docs, gold = build_corpus(base_dir)

    baselines: dict[str, callable] = {
        "ocr+regex": lambda d, p: predict_ocr_regex(d, p),
        "ocr+mock_vlm": lambda d, p: predict_pipeline(d, p, ocr="tesseract", structured="mock"),
    }
    if include_mesh:
        baselines["ocr+mesh_vlm"] = lambda d, p: predict_pipeline(
            d, p, ocr="tesseract", structured="mesh"
        )

    results: dict[str, dict] = {}
    for name, fn in baselines.items():
        predictions: dict[str, dict] = {}
        supported_all: list[bool] = []
        review_all: list[bool] = []
        for doc_id, pdf_path in docs:
            pred, supported, review = fn(doc_id, pdf_path)
            predictions[doc_id] = pred
            supported_all.extend(supported)
            review_all.append(review)
        results[name] = evaluate(
            predictions, gold, supported_flags=supported_all, review_flags=review_all
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 11 baseline comparison")
    parser.add_argument("--live", action="store_true", help="also run the real Mesh VLM")
    parser.add_argument("--out", default=str(settings.derived_dir / "eval"))
    args = parser.parse_args()

    if not TesseractOCRProvider().is_available():
        raise SystemExit("tesseract is required for the comparison runner.")

    out_dir = Path(args.out)
    corpus_dir = out_dir / "corpus"
    results = run_comparison(corpus_dir, include_mesh=args.live)

    csv_path = out_dir / "baseline_comparison.csv"
    md_path = out_dir / "baseline_comparison.md"
    write_report(results, csv_path=csv_path, md_path=md_path)

    print(f"\nWrote {csv_path}\nWrote {md_path}\n")
    for name, res in results.items():
        print(f"{name:14s}  P={res['precision']:.3f}  R={res['recall']:.3f}  "
              f"F1={res['f1']:.3f}  unsupported={res['unsupported_extraction_rate']:.3f}  "
              f"review={res['review_rate']:.3f}")


if __name__ == "__main__":
    main()
