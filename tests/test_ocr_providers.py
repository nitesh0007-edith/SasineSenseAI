from pathlib import Path

import pytest
from PIL import Image

from app.providers.factory import (
    get_ner_provider,
    get_ocr_provider,
    get_structured_provider,
)
from app.providers.mock_ocr import MockOCRProvider
from app.providers.tesseract_ocr import OCRUnavailableError, TesseractOCRProvider


def test_factory_selects_mock_ocr():
    assert isinstance(get_ocr_provider("mock"), MockOCRProvider)


def test_factory_selects_tesseract():
    assert isinstance(get_ocr_provider("tesseract"), TesseractOCRProvider)


def test_factory_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown OCR provider"):
        get_ocr_provider("does-not-exist")


def test_factory_ner_and_structured():
    assert get_ner_provider("spacy").name == "spacy"
    assert get_structured_provider("mock").name == "mock"


def test_tesseract_reports_availability():
    provider = TesseractOCRProvider()
    # Environment may or may not have tesseract; call must not raise here.
    assert isinstance(provider.is_available(), bool)


def test_tesseract_extract_graceful_when_unavailable(tmp_path: Path):
    provider = TesseractOCRProvider()
    if provider.is_available():
        pytest.skip("tesseract is installed in this environment")

    image_path = tmp_path / "page.png"
    Image.new("RGB", (60, 40), "white").save(image_path)
    with pytest.raises(OCRUnavailableError):
        provider.extract_page(image_path, page_number=1)
