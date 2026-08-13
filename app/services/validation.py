"""Deterministic validation and confidence scoring (Phase 8).

Validation rules are intentionally conservative and evidence-first: a field is
only "passed" when its extracted value is actually supported by its evidence
text. Confidence combines OCR confidence, source agreement, validation status
and evidence support. LLM self-reported confidence is treated as one weak signal
only, never as sufficient on its own.
"""

from __future__ import annotations

import re
from datetime import date

from app.core.config import settings
from app.models.schemas import ExtractedField, ValidationResult

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TITLE_REF = re.compile(r"^(?:[A-Z]{3}\d{4,6}|Book\s+\d+\s+Folio\s+\d+)$", re.I)
_BOILERPLATE_NAMES = {"john doe", "jane doe", "a.n. other", "test", "unknown"}


def _evidence_supports(field: ExtractedField) -> bool:
    """True when the extracted value (or its normalization) appears in evidence."""
    if not field.evidence:
        return False
    haystack = " ".join(span.text for span in field.evidence).casefold()
    for needle in (field.value, field.normalized_value):
        if needle is None:
            continue
        if str(needle).strip().casefold() in haystack:
            return True
    return False


def _date_parseable(field: ExtractedField) -> bool:
    normalized = field.normalized_value
    if isinstance(normalized, str) and _ISO_DATE.match(normalized):
        try:
            date.fromisoformat(normalized)
            return True
        except ValueError:
            return False
    return False


def validate_field(field: ExtractedField) -> ValidationResult:
    """Apply the rules relevant to a field's ``name`` and return a result."""
    passed: list[str] = []
    notes: list[str] = []
    failed = False

    value_str = "" if field.value is None else str(field.value).strip()
    if value_str:
        passed.append("non_empty")
    else:
        failed = True
        notes.append("value is empty")

    if _evidence_supports(field):
        passed.append("evidence_supported")
    else:
        failed = True
        notes.append("evidence does not contain extracted value")

    name = field.name
    if name == "document_date":
        if _date_parseable(field):
            passed.append("date_parseable")
        else:
            failed = True
            notes.append("date not parseable to ISO-8601")
    elif name == "title_reference":
        if _TITLE_REF.match(value_str):
            passed.append("title_reference_pattern")
        else:
            failed = True
            notes.append("title reference pattern invalid")
    elif name in {"party", "granter", "grantee"}:
        if value_str.casefold() in _BOILERPLATE_NAMES:
            failed = True
            notes.append("party name matches known boilerplate")
        else:
            passed.append("party_not_boilerplate")

    status: str
    if failed:
        status = "failed"
    elif len(passed) >= 2:
        status = "passed"
    else:
        status = "uncertain"

    return ValidationResult(status=status, rules=passed, notes=notes)


def compute_confidence(
    field: ExtractedField,
    *,
    ocr_confidence: float = 1.0,
    agreement: float = 0.0,
    validation: ValidationResult | None = None,
    model_confidence: float | None = None,
) -> float:
    """Weighted confidence in [0, 1].

    Weights: OCR 0.25, source agreement 0.20, validation 0.30, evidence 0.15,
    model self-report 0.10. Model confidence alone can never carry a field.
    """
    validation = validation or field.validation or validate_field(field)

    validation_score = {"passed": 1.0, "uncertain": 0.5, "failed": 0.0}[validation.status]
    evidence_score = 1.0 if _evidence_supports(field) else 0.0
    model_score = field.confidence if model_confidence is None else model_confidence

    score = (
        0.25 * max(0.0, min(1.0, ocr_confidence))
        + 0.20 * max(0.0, min(1.0, agreement))
        + 0.30 * validation_score
        + 0.15 * evidence_score
        + 0.10 * max(0.0, min(1.0, model_score))
    )
    return round(max(0.0, min(1.0, score)), 4)


def route_review(confidence: float) -> str:
    """Map a confidence score to a review tier. All outputs remain non-authoritative."""
    if confidence >= settings.review_high_confidence:
        return "high_confidence"
    if confidence >= settings.review_medium_confidence:
        return "quick_review"
    return "manual_review"


def review_required(confidence: float) -> bool:
    """High-confidence candidates skip mandatory review; everything else is routed."""
    return route_review(confidence) != "high_confidence"
