from app.models.schemas import EvidenceSpan, ExtractedField
from app.services.validation import (
    compute_confidence,
    review_required,
    route_review,
    validate_field,
)


def _field(name, value, normalized=None, evidence_text=None, method="regex", conf=0.9):
    evidence = []
    if evidence_text is not None:
        evidence = [EvidenceSpan(page=1, text=evidence_text, source="ocr_text")]
    return ExtractedField(
        name=name,
        value=value,
        normalized_value=normalized,
        confidence=conf,
        method=method,
        evidence=evidence,
    )


def test_validate_date_passes_with_evidence():
    field = _field(
        "document_date",
        "12 May 1876",
        normalized="1876-05-12",
        evidence_text="dated 12 May 1876",
    )
    result = validate_field(field)
    assert result.status == "passed"
    assert "date_parseable" in result.rules
    assert "evidence_supported" in result.rules


def test_validate_fails_without_evidence():
    field = _field("document_date", "12 May 1876", normalized="1876-05-12")
    result = validate_field(field)
    assert result.status == "failed"
    assert any("evidence" in note for note in result.notes)


def test_validate_bad_title_reference():
    field = _field("title_reference", "NOTAREF", evidence_text="ref NOTAREF here")
    result = validate_field(field)
    assert result.status == "failed"


def test_validate_boilerplate_party():
    field = _field("party", "John Doe", evidence_text="granted by John Doe")
    result = validate_field(field)
    assert result.status == "failed"
    assert any("boilerplate" in note for note in result.notes)


def test_confidence_higher_when_validated_and_agreeing():
    good = _field(
        "document_date", "12 May 1876", normalized="1876-05-12",
        evidence_text="dated 12 May 1876",
    )
    weak = _field("document_date", "12 May 1876", normalized="1876-05-12")

    good_score = compute_confidence(good, ocr_confidence=0.95, agreement=1.0)
    weak_score = compute_confidence(weak, ocr_confidence=0.4, agreement=0.0)
    assert good_score > weak_score
    assert 0.0 <= good_score <= 1.0


def test_model_confidence_alone_insufficient():
    # A field the model is "sure" about but with no evidence must not clear the
    # high-confidence bar on model confidence alone.
    field = _field("document_date", "12 May 1876", conf=1.0)
    score = compute_confidence(field, ocr_confidence=0.0, agreement=0.0, model_confidence=1.0)
    assert score < 0.90


def test_review_routing_tiers():
    assert route_review(0.95) == "high_confidence"
    assert route_review(0.80) == "quick_review"
    assert route_review(0.50) == "manual_review"
    assert review_required(0.95) is False
    assert review_required(0.80) is True
