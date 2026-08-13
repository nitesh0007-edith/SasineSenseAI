from pathlib import Path

from app.eval.harness import (
    comparison_report,
    evaluate,
    flatten_annotation,
    flatten_extraction,
    load_annotations,
    write_report,
)
from app.eval.metrics import (
    character_error_rate,
    exact_match,
    field_prf,
    review_rate,
    unsupported_extraction_rate,
    word_error_rate,
)
from app.services.pipeline import run_pipeline


def test_cer_wer_basic():
    assert character_error_rate("abc", "abc") == 0.0
    assert word_error_rate("the cat sat", "the cat sat") == 0.0
    assert character_error_rate("abc", "abd") > 0.0
    assert 0.0 < word_error_rate("the cat sat", "the dog sat") <= 1.0


def test_exact_match_normalizes():
    assert exact_match(" Glasgow ", "glasgow")
    assert exact_match(None, None)
    assert not exact_match("Glasgow", "Edinburgh")


def test_field_prf_counts():
    predicted = {"a": "x", "b": "wrong", "c": "z"}
    gold = {"a": "x", "b": "y", "d": "w"}
    prf = field_prf(predicted, gold)
    assert prf.true_positive == 1  # a
    assert prf.false_negative >= 1  # b mismatch + d missing
    assert 0.0 <= prf.f1 <= 1.0


def test_field_prf_multivalue_containment():
    # Richer prediction ("5 High Street, Glasgow") should still match gold
    # "Glasgow" item-for-item, and both parties count as true positives.
    predicted = {
        "places": "5 High Street, Glasgow|Craigmillar",
        "parties": "John Campbell|Mary Fraser",
    }
    gold = {"places": "Glasgow", "parties": "John Campbell|Mary Fraser"}
    prf = field_prf(predicted, gold)
    # 2 parties + 1 place matched = 3 true positives; "Craigmillar" is an extra
    # predicted place (false positive), no false negatives.
    assert prf.true_positive == 3
    assert prf.false_positive == 1
    assert prf.false_negative == 0
    assert prf.recall == 1.0


def test_reliability_rates():
    assert unsupported_extraction_rate([True, True, False, True]) == 0.25
    assert review_rate([True, False]) == 0.5
    assert unsupported_extraction_rate([]) == 0.0


def test_load_annotations_and_flatten(tmp_path: Path):
    jsonl = tmp_path / "gold.jsonl"
    jsonl.write_text(
        '{"document_id":"d1","document_type":"disposition",'
        '"fields":{"document_date":{"value":"1876-05-12"}},'
        '"parties":[{"name":"John Campbell"}],'
        '"places":[{"name":"Glasgow"}]}\n',
        encoding="utf-8",
    )
    items = load_annotations(jsonl)
    flat = flatten_annotation(items[0])
    assert flat["document_type"] == "disposition"
    assert flat["document_date"] == "1876-05-12"
    assert flat["parties"] == "John Campbell"
    assert flat["places"] == "Glasgow"


def test_evaluate_against_pipeline_prediction(tmp_path: Path):
    # Run the real mock pipeline and score it against a matching gold record.
    from PIL import Image

    image_path = tmp_path / "sample.png"
    Image.new("RGB", (400, 200), "white").save(image_path)
    extraction = run_pipeline("d1", str(image_path))

    predictions = {"d1": flatten_extraction(extraction)}
    gold = {
        "d1": {
            "document_type": "disposition",
            "document_date": "1876-05-12",
            "parties": "John Campbell|Mary Fraser",
            "places": "Glasgow",
        }
    }
    results = evaluate(
        predictions, gold, supported_flags=[True, True, True], review_flags=[True]
    )
    assert results["documents"] == 1
    assert results["f1"] > 0.5
    assert results["review_rate"] == 1.0


def test_comparison_report_and_write(tmp_path: Path):
    results = {
        "ocr_only": {"documents": 1, "precision": 0.5, "recall": 0.5, "f1": 0.5,
                     "unsupported_extraction_rate": 0.1, "review_rate": 0.9},
        "hybrid": {"documents": 1, "precision": 0.9, "recall": 0.9, "f1": 0.9,
                   "unsupported_extraction_rate": 0.02, "review_rate": 0.3},
    }
    csv_text, md_text = comparison_report(results)
    assert "baseline" in csv_text
    assert "hybrid" in md_text and "| ---" in md_text

    csv_path = tmp_path / "report.csv"
    md_path = tmp_path / "report.md"
    write_report(results, csv_path=csv_path, md_path=md_path)
    assert csv_path.is_file() and md_path.is_file()
