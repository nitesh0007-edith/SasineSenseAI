"""Candidate merge strategy (Phase 6.2).

Merges field candidates produced by different methods (regex, NER, VLM) into a
single :class:`MergedField`. Core principle: **never discard a conflicting
candidate silently**. Every candidate is preserved; agreement is scored; the
highest-confidence candidate is proposed but conflicts are flagged for review.
"""

from __future__ import annotations

from collections import Counter

from app.models.schemas import ExtractedField, MergedField


def _normalized_key(field: ExtractedField) -> str:
    """Compare on normalized value when present, else the raw value, casefolded."""
    value = field.normalized_value if field.normalized_value is not None else field.value
    return str(value).strip().casefold()


def merge_field_candidates(name: str, candidates: list[ExtractedField]) -> MergedField:
    """Merge candidates for a single field.

    Agreement is the fraction of candidates sharing the majority value. A
    conflict is recorded whenever two or more distinct values are present.
    Confidence of the chosen candidate is boosted by cross-method agreement so
    that independent methods converging raises trust.
    """
    if not candidates:
        return MergedField(name=name)

    methods = sorted({c.method for c in candidates})
    value_counts = Counter(_normalized_key(c) for c in candidates)
    majority_key, majority_count = value_counts.most_common(1)[0]
    agreement = majority_count / len(candidates)
    conflict = len(value_counts) > 1

    # Choose among the majority-value candidates by confidence; if that value is
    # backed by multiple distinct methods, nudge confidence upward (capped).
    majority_candidates = [c for c in candidates if _normalized_key(c) == majority_key]
    chosen = max(majority_candidates, key=lambda c: c.confidence)
    distinct_methods = len({c.method for c in majority_candidates})
    if distinct_methods > 1:
        boosted = min(1.0, chosen.confidence + 0.05 * (distinct_methods - 1))
        chosen = chosen.model_copy(update={"confidence": boosted})

    return MergedField(
        name=name,
        chosen=chosen,
        candidates=list(candidates),
        methods=methods,
        agreement=round(agreement, 3),
        conflict=conflict,
    )


def merge_grouped_candidates(
    grouped: dict[str, list[ExtractedField]],
) -> dict[str, MergedField]:
    """Merge a mapping of field-name -> candidate list into merged fields."""
    return {name: merge_field_candidates(name, cands) for name, cands in grouped.items()}
