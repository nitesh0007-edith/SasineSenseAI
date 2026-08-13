"""Provider selection by config (keeps providers out of business logic).

Business code asks the factory for a provider by name; the concrete adapter is
chosen from settings/env. This is what lets OCR/NER/structured providers be
swapped without touching the pipeline.
"""

from __future__ import annotations

from app.core.config import settings
from app.providers.base import NERProvider, OCRProvider, StructuredExtractionProvider
from app.providers.gazetteer import GazetteerPlaceResolver
from app.providers.mock_ocr import MockOCRProvider
from app.providers.mock_structured import MockStructuredExtractionProvider
from app.providers.spacy_ner import SpacyNERProvider


def get_ocr_provider(name: str | None = None) -> OCRProvider:
    name = (name or settings.ocr_provider).lower()
    if name == "mock":
        return MockOCRProvider()
    if name == "tesseract":
        from app.providers.tesseract_ocr import TesseractOCRProvider

        return TesseractOCRProvider()
    raise ValueError(f"Unknown OCR provider: {name!r}")


def get_ner_provider(name: str | None = None) -> NERProvider:
    name = (name or settings.ner_provider).lower()
    if name == "spacy":
        return SpacyNERProvider()
    raise ValueError(f"Unknown NER provider: {name!r}")


def get_structured_provider(name: str | None = None) -> StructuredExtractionProvider:
    name = (name or settings.structured_extraction_provider).lower()
    if name == "mock":
        return MockStructuredExtractionProvider()
    if name == "mesh":
        from app.providers.mesh_structured import MeshStructuredExtractionProvider

        return MeshStructuredExtractionProvider()
    raise ValueError(f"Unknown structured extraction provider: {name!r}")


def get_place_resolver() -> GazetteerPlaceResolver:
    return GazetteerPlaceResolver()
