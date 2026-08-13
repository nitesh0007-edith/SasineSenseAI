"""Run the extraction pipeline over an authorized local document folder.

Usage::

    python -m app.batch.run --input-dir ./data/source_records \
        --output ./data/derived/batch/results.jsonl

The runner is deliberately conservative: one failed document does not stop the
batch, every output keeps its source path and provider metadata, and failures
are emitted as JSONL records for audit/retry. It does not download or discover
records from external archives.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
from pathlib import Path

from app.core.config import settings
from app.db.repository import DocumentRepository
from app.models.schemas import DocumentRecord
from app.services.pipeline import run_pipeline

SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def discover_documents(input_dir: Path, *, recursive: bool = True) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    return sorted(
        path
        for path in input_dir.glob(pattern)
        if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES
    )


def stable_document_id(path: Path) -> str:
    """Create a repeatable ID from file bytes, useful for safe re-runs."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:24]
    return f"doc_batch_{digest}"


def _document_record(path: Path, document_id: str) -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id,
        filename=path.name,
        media_type=mimetypes.guess_type(path.name)[0],
        size_bytes=path.stat().st_size,
        local_path=str(path.resolve()),
    )


def process_documents(
    paths: list[Path],
    *,
    output_path: Path,
    persist: bool = True,
    ocr_provider: str | None = None,
    structured_provider: str | None = None,
) -> dict[str, int]:
    """Process paths and write one result/error object per line."""
    old_ocr = settings.ocr_provider
    old_structured = settings.structured_extraction_provider
    if ocr_provider:
        settings.ocr_provider = ocr_provider
    if structured_provider:
        settings.structured_extraction_provider = structured_provider

    repository = DocumentRepository() if persist else None
    counts = {"discovered": len(paths), "processed": 0, "failed": 0}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("w", encoding="utf-8") as output:
            for path in paths:
                document_id = stable_document_id(path)
                record = _document_record(path, document_id)
                try:
                    if repository:
                        repository.save_document(record)
                    extraction = run_pipeline(document_id, str(path))
                    if repository:
                        repository.save_extraction(extraction)
                    payload = {
                        "status": "processed",
                        "document_id": document_id,
                        "source_file": str(path),
                        "source_filename": path.name,
                        "extraction": extraction.model_dump(mode="json"),
                    }
                    counts["processed"] += 1
                except Exception as exc:  # keep the batch moving; record the failure
                    payload = {
                        "status": "failed",
                        "document_id": document_id,
                        "source_file": str(path),
                        "source_filename": path.name,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                    counts["failed"] += 1
                output.write(json.dumps(payload, ensure_ascii=False) + "\n")
    finally:
        if repository:
            repository.close()
        settings.ocr_provider = old_ocr
        settings.structured_extraction_provider = old_structured

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch process authorized sasine/deed files")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.derived_dir / "batch" / "results.jsonl",
    )
    parser.add_argument("--no-persist", action="store_true", help="skip database writes")
    parser.add_argument("--flat", action="store_true", help="do not scan subdirectories")
    parser.add_argument("--limit", type=int, default=0, help="process at most N files")
    parser.add_argument("--ocr", help="temporary OCR provider override, e.g. tesseract")
    parser.add_argument("--structured", help="temporary structured provider override, e.g. mesh")
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        raise SystemExit(f"Input directory does not exist: {args.input_dir}")
    paths = discover_documents(args.input_dir, recursive=not args.flat)
    if args.limit > 0:
        paths = paths[: args.limit]
    counts = process_documents(
        paths,
        output_path=args.output,
        persist=not args.no_persist,
        ocr_provider=args.ocr,
        structured_provider=args.structured,
    )
    print(json.dumps({**counts, "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
