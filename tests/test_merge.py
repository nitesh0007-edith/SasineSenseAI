from app.models.schemas import ExtractedField
from app.services.merge import merge_field_candidates, merge_grouped_candidates


def _field(value, method, conf, normalized=None):
    return ExtractedField(
        name="document_date",
        value=value,
        normalized_value=normalized,
        confidence=conf,
        method=method,
    )


def test_merge_empty():
    merged = merge_field_candidates("document_date", [])
    assert merged.chosen is None
    assert merged.candidates == []
    assert merged.agreement == 0.0


def test_merge_agreement_boosts_confidence():
    candidates = [
        _field("12 May 1876", "regex", 0.80, normalized="1876-05-12"),
        _field("12 May 1876", "mock_vlm", 0.85, normalized="1876-05-12"),
    ]
    merged = merge_field_candidates("document_date", candidates)

    assert merged.agreement == 1.0
    assert merged.conflict is False
    assert merged.methods == ["mock_vlm", "regex"]
    # Two distinct methods agree -> confidence boosted above the max input.
    assert merged.chosen.confidence > 0.85


def test_merge_preserves_conflicts():
    candidates = [
        _field("12 May 1876", "regex", 0.70, normalized="1876-05-12"),
        _field("13 May 1876", "mock_vlm", 0.90, normalized="1876-05-13"),
    ]
    merged = merge_field_candidates("document_date", candidates)

    assert merged.conflict is True
    assert len(merged.candidates) == 2  # nothing dropped
    assert merged.agreement == 0.5
    # Majority tie broken by confidence within the majority value; here each
    # value has one vote so majority_count == 1 -> agreement 0.5, chosen is
    # the most_common first value.
    assert merged.chosen is not None


def test_merge_grouped():
    grouped = {
        "document_date": [_field("12 May 1876", "regex", 0.8, normalized="1876-05-12")],
        "money": [
            ExtractedField(name="money", value="£500", confidence=0.85, method="regex")
        ],
    }
    result = merge_grouped_candidates(grouped)
    assert set(result) == {"document_date", "money"}
    assert result["money"].chosen.value == "£500"
