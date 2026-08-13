from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class EvidenceSpan(BaseModel):
    page: int
    text: str
    bbox: BoundingBox | None = None
    source: str


class ValidationResult(BaseModel):
    status: Literal["passed", "failed", "uncertain"]
    rules: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ExtractedField(BaseModel):
    name: str
    value: str | int | float | bool | None
    normalized_value: str | int | float | bool | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    method: str
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    validation: ValidationResult | None = None


class Party(BaseModel):
    name: str
    role: Literal["seller", "buyer", "owner", "granter", "grantee", "unknown"] = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[EvidenceSpan] = Field(default_factory=list)


class PlaceCandidate(BaseModel):
    name: str
    normalized_name: str | None = None
    admin_area: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[EvidenceSpan] = Field(default_factory=list)


class OCRToken(BaseModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox | None = None


class OCRPageResult(BaseModel):
    page: int
    text: str
    tokens: list[OCRToken] = Field(default_factory=list)
    provider: str
    provider_version: str | None = None


class PropertyRecordExtraction(BaseModel):
    document_id: str
    document_type: Literal[
        "sasine",
        "disposition",
        "deed",
        "title_sheet",
        "property_form",
        "unknown",
    ] = "unknown"
    document_date: ExtractedField | None = None
    parties: list[Party] = Field(default_factory=list)
    property_description: ExtractedField | None = None
    consideration: ExtractedField | None = None
    places: list[PlaceCandidate] = Field(default_factory=list)
    rights: list[ExtractedField] = Field(default_factory=list)
    burdens: list[ExtractedField] = Field(default_factory=list)
    servitudes: list[ExtractedField] = Field(default_factory=list)
    title_references: list[ExtractedField] = Field(default_factory=list)
    map_references: list[ExtractedField] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)
    review_required: bool = True
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRecord(BaseModel):
    document_id: str
    filename: str
    media_type: str | None = None
    size_bytes: int
    local_path: str
    created_at: datetime = Field(default_factory=utc_now)


class RenderedPage(BaseModel):
    page_number: int = Field(ge=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    local_image_path: Path


class PreprocessResult(BaseModel):
    """Output of image preprocessing (Phase 2).

    The original image is never mutated; ``processed_image_path`` points at a
    derived copy. When no operations run, it equals ``original_image_path``.
    """

    original_image_path: Path
    processed_image_path: Path
    operations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityCandidate(BaseModel):
    """A normalized NER candidate with provenance (Phase 5)."""

    text: str
    label: str  # PERSON, ORG, GPE, LOC, DATE, or custom pattern label
    normalized_text: str | None = None
    start_char: int
    end_char: int
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    method: str = "spacy"
    evidence: list[EvidenceSpan] = Field(default_factory=list)


class MergedField(BaseModel):
    """Result of merging candidate values for one field (Phase 6.2).

    All candidates are preserved. ``chosen`` is the highest-scoring candidate but
    conflicting alternatives remain visible in ``candidates`` and are never
    dropped silently.
    """

    name: str
    chosen: ExtractedField | None = None
    candidates: list[ExtractedField] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    agreement: float = Field(default=0.0, ge=0.0, le=1.0)
    conflict: bool = False


class ReviewAction(BaseModel):
    """An append-only reviewer decision (Phase 10). History is never deleted."""

    document_id: str
    field: str
    action: Literal["accept", "edit", "flag", "mark_unresolved"]
    previous_value: str | int | float | bool | None = None
    new_value: str | int | float | bool | None = None
    reviewer: str | None = None
    note: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)
