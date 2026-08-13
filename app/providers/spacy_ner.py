"""spaCy-based NER provider with Scottish legal EntityRuler patterns (Phase 5).

Loads ``en_core_web_sm`` when available for statistical PERSON/ORG/GPE/DATE, and
always layers deterministic ``EntityRuler`` patterns for legal/deed vocabulary so
the provider stays useful even on a blank pipeline. Model loading is lazy and
cached so importing this module never forces a download.
"""

from __future__ import annotations

from functools import lru_cache

from app.models.schemas import EntityCandidate, EvidenceSpan, OCRPageResult

KEPT_LABELS = {"PERSON", "ORG", "GPE", "LOC", "DATE", "FAC"}

# Deterministic legal/deed patterns. Labels are custom, uppercased.
LEGAL_PATTERNS: list[dict] = [
    {"label": "LANDS", "pattern": [{"LOWER": "lands"}, {"LOWER": "of"}, {"IS_TITLE": True, "OP": "+"}]},
    {"label": "PLACE_CUE", "pattern": [{"LOWER": "situated"}, {"LOWER": {"IN": ["at", "in"]}}, {"IS_TITLE": True, "OP": "+"}]},
    {"label": "PARTY_ROLE", "pattern": [{"LOWER": {"IN": ["granter", "grantee", "disponer", "disponee"]}}]},
    {"label": "COUNTY", "pattern": [{"LOWER": "county"}, {"LOWER": "of"}, {"IS_TITLE": True, "OP": "+"}]},
    {"label": "PARISH", "pattern": [{"LOWER": "parish"}, {"LOWER": "of"}, {"IS_TITLE": True, "OP": "+"}]},
    {"label": "DEED_TERM", "pattern": [{"LOWER": {"IN": ["sasine", "disposition", "assignation", "discharge", "conveyance"]}}]},
]


@lru_cache(maxsize=1)
def _load_nlp():
    import spacy

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        # TODO: `python -m spacy download en_core_web_sm` for statistical NER.
        # Blank pipeline still supports the deterministic EntityRuler patterns.
        nlp = spacy.blank("en")

    if "entity_ruler" not in nlp.pipe_names:
        ruler = nlp.add_pipe("entity_ruler", after="ner" if "ner" in nlp.pipe_names else None)
        ruler.add_patterns(LEGAL_PATTERNS)
    return nlp


class SpacyNERProvider:
    name = "spacy"

    def __init__(self, min_confidence: float = 0.5) -> None:
        self._min_confidence = min_confidence

    def extract_entities(self, page: OCRPageResult) -> list[EntityCandidate]:
        nlp = _load_nlp()
        doc = nlp(page.text)
        candidates: list[EntityCandidate] = []
        custom_labels = {p["label"] for p in LEGAL_PATTERNS}
        for ent in doc.ents:
            is_custom = ent.label_ in custom_labels
            if not is_custom and ent.label_ not in KEPT_LABELS:
                continue
            # Statistical entities and custom rule entities both retained;
            # rule-based ones get a fixed higher confidence.
            confidence = 0.75 if is_custom else 0.70
            try:
                evidence_text = ent.sent.text
            except (ValueError, AttributeError):
                evidence_text = ent.text
            candidates.append(
                EntityCandidate(
                    text=ent.text,
                    label=ent.label_,
                    normalized_text=ent.text.strip(),
                    start_char=ent.start_char,
                    end_char=ent.end_char,
                    confidence=confidence,
                    method="spacy_ruler" if is_custom else "spacy_ner",
                    evidence=[
                        EvidenceSpan(
                            page=page.page,
                            text=evidence_text,
                            bbox=None,
                            source="ocr_text",
                        )
                    ],
                )
            )
        return candidates
