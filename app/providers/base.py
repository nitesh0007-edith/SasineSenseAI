from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.models.schemas import (
    EntityCandidate,
    OCRPageResult,
    PlaceCandidate,
    PropertyRecordExtraction,
)


class OCRProvider(Protocol):
    name: str

    def extract_page(self, image_path: Path, page_number: int) -> OCRPageResult: ...


class NERProvider(Protocol):
    name: str

    def extract_entities(self, page: OCRPageResult) -> list[EntityCandidate]: ...


class PlaceResolver(Protocol):
    name: str

    def resolve(self, place_name: str, *, limit: int = 5) -> list[PlaceCandidate]: ...


class StructuredExtractionProvider(Protocol):
    name: str

    def extract(
        self,
        *,
        document_id: str,
        ocr_pages: list[OCRPageResult],
        page_images: list[Path],
        context: dict | None = None,
    ) -> PropertyRecordExtraction: ...
