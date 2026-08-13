"""Hybrid extraction pipeline (wires Phases 1–9 together).

Flow: render -> optional preprocess -> OCR -> regex + NER candidates ->
structured (mock VLM) -> merge candidates -> validate + score -> resolve places
-> route review. Providers are chosen via the factory (config-driven), so no
concrete OCR/NER/VLM implementation is hard-wired into this business logic.

All extracted values keep evidence; conflicting candidates are preserved in
``metadata`` rather than dropped. Outputs remain non-authoritative.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.models.schemas import Party, PlaceCandidate, PropertyRecordExtraction
from app.providers.factory import (
    get_ner_provider,
    get_ocr_provider,
    get_place_resolver,
    get_structured_provider,
)
from app.services.merge import merge_field_candidates
from app.services.preprocessing import PreprocessConfig, preprocess_image
from app.services.rendering import render_document
from app.services.rules import classify_document_type, extract_all, extract_map_references
from app.services.validation import (
    compute_confidence,
    review_required,
    route_review,
    validate_field,
)


def _dedupe_fields(fields):
    """Collapse repeated OCR matches while retaining all evidence spans."""
    by_value = {}
    for field in fields:
        key = str(field.normalized_value or field.value).strip().casefold()
        existing = by_value.get(key)
        if existing is None:
            by_value[key] = field
            continue
        evidence = existing.evidence + [span for span in field.evidence if span not in existing.evidence]
        by_value[key] = existing.model_copy(update={"evidence": evidence})
    return list(by_value.values())


def run_pipeline(document_id: str, local_path: str) -> PropertyRecordExtraction:
    path = Path(local_path)
    rendered_pages = render_document(path, document_id=document_id)
    page_images = [Path(page.local_image_path) for page in rendered_pages]

    # Phase 2 — optional preprocessing (non-destructive; toggled by config).
    preprocess_ops: list[str] = []
    if settings.preprocess_enabled:
        cfg = PreprocessConfig.from_settings()
        processed: list[Path] = []
        for image_path in page_images:
            result = preprocess_image(image_path, config=cfg)
            processed.append(Path(result.processed_image_path))
            preprocess_ops = result.operations
        page_images = processed

    # Phase 3 — OCR (provider selected by config).
    ocr = get_ocr_provider()
    ocr_pages = [
        ocr.extract_page(image_path=image_path, page_number=page.page_number)
        for image_path, page in zip(page_images, rendered_pages, strict=True)
    ]

    # Phase 4 & 5 — deterministic regex + NER candidates (evidence-bearing).
    regex_by_page = [extract_all(p) for p in ocr_pages]
    ner = get_ner_provider()
    entity_candidates = [ent for p in ocr_pages for ent in ner.extract_entities(p)]

    # Phase 7 — structured extraction (mock VLM by default).
    structured = get_structured_provider()
    result = structured.extract(
        document_id=document_id,
        ocr_pages=ocr_pages,
        page_images=page_images,
    )

    combined_text = "\n".join(p.text for p in ocr_pages)
    deterministic_type = classify_document_type(combined_text)
    if deterministic_type != "unknown":
        result.document_type = deterministic_type  # type: ignore[assignment]

    # Phase 6.2 — merge date candidates from regex and the structured provider.
    date_candidates = [c for page in regex_by_page for c in page["dates"]]
    structured_date = result.document_date
    if structured_date is not None:
        date_candidates.append(structured_date)
    merged_date = merge_field_candidates("document_date", date_candidates)

    review_flags: list[bool] = []
    resolver = get_place_resolver()
    # A title register commonly contains search, registration, update and entry
    # dates. Without a field label, selecting one as the document date is unsafe.
    if merged_date.chosen is not None and not (
        deterministic_type == "title_sheet"
        and merged_date.conflict
        and structured_date is None
    ):
        chosen = merged_date.chosen
        validation = validate_field(chosen)
        best_ocr = max(
            (t.confidence for p in ocr_pages for t in p.tokens),
            default=1.0,
        )
        confidence = compute_confidence(
            chosen,
            ocr_confidence=best_ocr,
            agreement=merged_date.agreement,
            validation=validation,
        )
        chosen = chosen.model_copy(update={"confidence": confidence, "validation": validation})
        result.document_date = chosen
        review_flags.append(review_required(confidence))

    # Promote deterministic candidates into the structured result when the
    # configured structured provider has no value. This keeps title-register
    # outputs useful even without a VLM, while retaining evidence and review.
    flat_regex = {
        key: [field for page in regex_by_page for field in page[key]]
        for key in ("money", "postcodes", "title_references", "reference_numbers")
    }
    map_candidates = [extract_map_references(page) for page in ocr_pages]
    flat_map_references = [field for page in map_candidates for field in page]
    if not result.title_references:
        result.title_references = _dedupe_fields(flat_regex["title_references"])
    if not result.map_references:
        result.map_references = _dedupe_fields(flat_map_references)
    if result.consideration is None and flat_regex["money"]:
        result.consideration = _dedupe_fields(flat_regex["money"])[0].model_copy(
            update={"name": "consideration"}
        )

    if not result.parties and deterministic_type != "title_sheet":
        for entity in entity_candidates:
            if entity.label not in {"PERSON", "ORG"}:
                continue
            result.parties.append(
                Party(
                    name=entity.text,
                    role="owner" if deterministic_type == "title_sheet" else "unknown",
                    confidence=entity.confidence,
                    evidence=entity.evidence,
                )
            )
    if not result.places:
        for entity in entity_candidates:
            if entity.label not in {"GPE", "LOC"}:
                continue
            if not resolver.resolve(entity.text, limit=1):
                continue
            result.places.append(
                PlaceCandidate(
                    name=entity.text,
                    confidence=entity.confidence,
                    evidence=entity.evidence,
                )
            )

    # Phase 9 — resolve places against the local gazetteer (ranked, non-forcing).
    for place in result.places:
        matches = resolver.resolve(place.name, limit=3)
        if matches:
            top = matches[0]
            place.normalized_name = top.normalized_name
            place.admin_area = top.admin_area
            place.latitude = top.latitude
            place.longitude = top.longitude
            place.confidence = max(place.confidence, top.confidence)
        review_flags.append(review_required(place.confidence))

    # Aggregate confidence + review routing (Phase 8).
    field_confidences = [p.confidence for p in result.parties]
    field_confidences += [p.confidence for p in result.places]
    field_confidences += [p.confidence for p in result.title_references]
    field_confidences += [p.confidence for p in result.map_references]
    if result.document_date is not None:
        field_confidences.append(result.document_date.confidence)
    if result.consideration is not None:
        field_confidences.append(result.consideration.confidence)
    overall = round(sum(field_confidences) / len(field_confidences), 4) if field_confidences else 0.0
    result.overall_confidence = overall
    result.review_required = any(review_flags) or review_required(overall)
    result.source_pages = [p.page for p in ocr_pages]

    # Preserve all candidates and provenance rather than dropping conflicts.
    result.metadata.update(
        {
            "ocr_provider": ocr.name,
            "ner_provider": ner.name,
            "structured_provider": structured.name,
            "preprocess_operations": preprocess_ops,
            "review_tier": route_review(overall),
            "entity_candidate_count": len(entity_candidates),
            "date_candidates": [c.model_dump(mode="json") for c in merged_date.candidates],
            "date_conflict": merged_date.conflict,
            "regex_candidates": {
                key: [f.model_dump(mode="json") for page in regex_by_page for f in page[key]]
                for key in ("money", "postcodes", "title_references", "reference_numbers")
            },
            "map_reference_candidates": [
                f.model_dump(mode="json") for f in flat_map_references
            ],
        }
    )

    return result
