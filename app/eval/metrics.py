"""Evaluation metrics (Phase 11).

Pure, deterministic functions. Character/word error rates use Levenshtein edit
distance; field-level scoring uses set-style precision/recall/F1 over
name->value pairs. Also included: reliability metrics (unsupported extraction
rate, review rate) that are central to the project's research question.
"""

from __future__ import annotations

from dataclasses import dataclass


def levenshtein(a: list[str] | str, b: list[str] | str) -> int:
    """Edit distance over sequences (characters or tokens)."""
    if a == b:
        return 0
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[n]


def character_error_rate(reference: str, hypothesis: str) -> float:
    """CER = edit_distance(chars) / len(reference_chars)."""
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return levenshtein(reference, hypothesis) / len(reference)


def word_error_rate(reference: str, hypothesis: str) -> float:
    """WER = edit_distance(tokens) / len(reference_tokens)."""
    ref_tokens = reference.split()
    hyp_tokens = hypothesis.split()
    if not ref_tokens:
        return 0.0 if not hyp_tokens else 1.0
    return levenshtein(ref_tokens, hyp_tokens) / len(ref_tokens)


def exact_match(predicted: str | None, gold: str | None) -> bool:
    """Case/whitespace-insensitive equality; two None values count as a match."""
    def norm(v: str | None) -> str | None:
        return None if v is None else str(v).strip().casefold()

    return norm(predicted) == norm(gold)


@dataclass
class PRF:
    precision: float
    recall: float
    f1: float
    true_positive: int
    false_positive: int
    false_negative: int


def _items(value: str) -> list[str]:
    """Split a pipe-delimited multi-value field into normalized items."""
    return [part.strip().casefold() for part in str(value).split("|") if part.strip()]


def _set_counts(predicted: str, gold: str) -> tuple[int, int, int]:
    """Item-level tp/fp/fn for multi-value fields with containment matching.

    A predicted item matches a gold item when either string contains the other
    (case-insensitive). This gives fair credit for granularity differences, e.g.
    predicted "5 High Street, Glasgow" satisfies gold "Glasgow".
    """
    pred_items = _items(predicted)
    gold_items = _items(gold)
    matched_gold: set[int] = set()
    tp = 0
    for p in pred_items:
        for gi, g in enumerate(gold_items):
            if gi in matched_gold:
                continue
            if p == g or p in g or g in p:
                tp += 1
                matched_gold.add(gi)
                break
    fp = len(pred_items) - tp
    fn = len(gold_items) - len(matched_gold)
    return tp, fp, fn


def field_prf(
    predicted: dict[str, str | None],
    gold: dict[str, str | None],
) -> PRF:
    """Precision/recall/F1 over field name->value pairs.

    Single-value fields use exact match. Multi-value fields (pipe-delimited,
    e.g. parties/places) are scored item-by-item with containment matching so
    richer-but-correct extraction is not unfairly penalized.
    """
    tp = fp = fn = 0
    keys = set(predicted) | set(gold)
    for key in keys:
        p = predicted.get(key)
        g = gold.get(key)
        p_present = p is not None and str(p).strip() != ""
        g_present = g is not None and str(g).strip() != ""
        multi = (p_present and "|" in str(p)) or (g_present and "|" in str(g))

        if multi:
            dtp, dfp, dfn = _set_counts(str(p) if p_present else "",
                                        str(g) if g_present else "")
            tp += dtp
            fp += dfp
            fn += dfn
        elif p_present and g_present:
            if exact_match(p, g):
                tp += 1
            else:
                fp += 1
                fn += 1
        elif p_present and not g_present:
            fp += 1
        elif g_present and not p_present:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return PRF(round(precision, 4), round(recall, 4), round(f1, 4), tp, fp, fn)


def unsupported_extraction_rate(supported_flags: list[bool]) -> float:
    """Fraction of extracted fields whose value is NOT supported by evidence."""
    if not supported_flags:
        return 0.0
    unsupported = sum(1 for s in supported_flags if not s)
    return round(unsupported / len(supported_flags), 4)


def review_rate(review_flags: list[bool]) -> float:
    """Fraction of documents/fields routed to human review."""
    if not review_flags:
        return 0.0
    return round(sum(1 for r in review_flags if r) / len(review_flags), 4)
