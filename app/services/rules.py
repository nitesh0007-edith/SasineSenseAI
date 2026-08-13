from __future__ import annotations

import re
from datetime import date

from app.models.schemas import EvidenceSpan, ExtractedField, OCRPageResult

DATE_PATTERNS = [
    re.compile(
        r"\b(?P<day>\d{1,2})\s+"
        r"(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+"
        r"(?P<year>\d{4})\b",
        re.I,
    ),
]

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# Weighted keyword cues per document type. More specific cues score higher so a
# document mentioning several terms is classified by the strongest signal rather
# than by dict ordering.
DOC_KEYWORDS: dict[str, dict[str, float]] = {
    "sasine": {"sasine": 3.0, "instrument of sasine": 4.0, "register of sasines": 4.0},
    "disposition": {"disposition": 3.0, "dispone": 2.0, "in favour of": 1.0},
    "deed": {"deed": 2.0, "deed of": 2.5, "assignation": 2.0, "discharge": 1.5},
    "title_sheet": {"title sheet": 4.0, "land certificate": 3.0, "title number": 2.0},
    "property_form": {"property form": 4.0, "application form": 2.0},
}

# UK/Scottish reference patterns. These are deliberately conservative.
MONEY_PATTERN = re.compile(r"£\s?\d[\d,]*(?:\.\d{1,2})?", re.I)
POSTCODE_PATTERN = re.compile(
    r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b",
)
# Scottish title numbers, e.g. GLA123456, ANG12345; and Book/Folio references.
TITLE_REF_PATTERN = re.compile(
    r"\b(?:[A-Z]{3}\d{4,6}|Book\s+\d+\s+Folio\s+\d+)\b",
    re.I,
)
REFERENCE_NUMBER_PATTERN = re.compile(
    r"\b(?:No\.?|Ref\.?|Reference|Page)\s*[:#]?\s*(\d{1,6})\b",
    re.I,
)
DEED_KEYWORDS = (
    "disposition",
    "sasine",
    "assignation",
    "discharge",
    "conveyance",
    "feu charter",
    "feu contract",
    "burden",
    "servitude",
    "granter",
    "grantee",
    "dispone",
    "in favour of",
    "heritably and irredeemably",
)


def classify_document_type_scores(text: str) -> dict[str, float]:
    """Return a score per document type. Higher is a stronger match."""
    lowered = text.lower()
    scores: dict[str, float] = {}
    for label, cues in DOC_KEYWORDS.items():
        score = sum(weight for cue, weight in cues.items() if cue in lowered)
        if score:
            scores[label] = score
    return scores


def classify_document_type(text: str) -> str:
    """Deterministic best-label classifier. Returns ``unknown`` when no cue matches."""
    scores = classify_document_type_scores(text)
    if not scores:
        return "unknown"
    return max(scores, key=lambda label: scores[label])


def extract_dates(page: OCRPageResult) -> list[ExtractedField]:
    results: list[ExtractedField] = []

    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(page.text):
            raw = match.group(0)
            try:
                parsed = date(
                    int(match.group("year")),
                    MONTHS[match.group("month")[:3].lower()],
                    int(match.group("day")),
                )
            except ValueError:
                parsed = None
            normalized = parsed.isoformat() if parsed else None
            results.append(
                ExtractedField(
                    name="document_date",
                    value=raw,
                    normalized_value=normalized,
                    confidence=0.90 if parsed else 0.60,
                    method="regex",
                    evidence=[
                        EvidenceSpan(
                            page=page.page,
                            text=raw,
                            bbox=None,
                            source="ocr_text",
                        )
                    ],
                )
            )
    return results


def _fields_from_pattern(
    page: OCRPageResult,
    pattern: re.Pattern[str],
    *,
    name: str,
    confidence: float,
    group: int = 0,
) -> list[ExtractedField]:
    """Generic deterministic extractor yielding an ExtractedField per match.

    Evidence text is the raw match; regex operates on OCR text so no bbox is
    available (word boxes belong to the OCR layer).
    """
    fields: list[ExtractedField] = []
    for match in pattern.finditer(page.text):
        raw = match.group(group)
        fields.append(
            ExtractedField(
                name=name,
                value=raw,
                normalized_value=raw.strip(),
                confidence=confidence,
                method="regex",
                evidence=[
                    EvidenceSpan(
                        page=page.page,
                        text=match.group(0),
                        bbox=None,
                        source="ocr_text",
                    )
                ],
            )
        )
    return fields


def extract_money(page: OCRPageResult) -> list[ExtractedField]:
    return _fields_from_pattern(page, MONEY_PATTERN, name="money", confidence=0.85)


def extract_postcodes(page: OCRPageResult) -> list[ExtractedField]:
    return _fields_from_pattern(page, POSTCODE_PATTERN, name="postcode", confidence=0.80)


def extract_title_references(page: OCRPageResult) -> list[ExtractedField]:
    return _fields_from_pattern(
        page, TITLE_REF_PATTERN, name="title_reference", confidence=0.75
    )


def extract_reference_numbers(page: OCRPageResult) -> list[ExtractedField]:
    return _fields_from_pattern(
        page, REFERENCE_NUMBER_PATTERN, name="reference_number", confidence=0.70, group=1
    )


def extract_deed_keywords(page: OCRPageResult) -> list[ExtractedField]:
    """Surface obvious deed vocabulary as low-weight, evidence-bearing signals."""
    lowered = page.text.lower()
    fields: list[ExtractedField] = []
    for keyword in DEED_KEYWORDS:
        start = lowered.find(keyword)
        if start == -1:
            continue
        raw = page.text[start : start + len(keyword)]
        fields.append(
            ExtractedField(
                name="deed_keyword",
                value=keyword,
                normalized_value=keyword,
                confidence=0.60,
                method="regex",
                evidence=[
                    EvidenceSpan(page=page.page, text=raw, bbox=None, source="ocr_text")
                ],
            )
        )
    return fields


def extract_all(page: OCRPageResult) -> dict[str, list[ExtractedField]]:
    """Run every deterministic extractor over a page (Phase 4 baseline)."""
    return {
        "dates": extract_dates(page),
        "money": extract_money(page),
        "postcodes": extract_postcodes(page),
        "title_references": extract_title_references(page),
        "reference_numbers": extract_reference_numbers(page),
        "deed_keywords": extract_deed_keywords(page),
    }
