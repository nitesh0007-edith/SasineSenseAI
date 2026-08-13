from pathlib import Path

import pytest

from app.eval.run import build_corpus, run_comparison
from app.providers.tesseract_ocr import TesseractOCRProvider

requires_tesseract = pytest.mark.skipif(
    not TesseractOCRProvider().is_available(),
    reason="tesseract binary not installed",
)


def test_build_corpus(tmp_path: Path):
    docs, gold = build_corpus(tmp_path)
    assert len(docs) == 2
    assert set(gold) == {"syneval_001", "syneval_002"}
    for _, pdf in docs:
        assert pdf.is_file()


@requires_tesseract
def test_comparison_no_network(tmp_path: Path):
    # Only the non-live baselines (no Mesh call).
    results = run_comparison(tmp_path, include_mesh=False)
    assert set(results) == {"ocr+regex", "ocr+mock_vlm"}
    for res in results.values():
        assert res["documents"] == 2
        assert 0.0 <= res["f1"] <= 1.0
    # The mock VLM is hand-tuned to document 1, so it must not achieve perfect
    # recall across the two-document corpus.
    assert results["ocr+mock_vlm"]["recall"] < 1.0
