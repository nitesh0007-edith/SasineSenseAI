"""Tesseract OCR adapter (Phase 3.3).

A real OCR provider behind the :class:`OCRProvider` interface. It is *not* wired
into business logic directly — selection happens via config (``OCR_PROVIDER``).
Both the ``pytesseract`` Python package and the ``tesseract`` binary are optional
runtime dependencies; when either is missing, :meth:`extract_page` raises a clear
:class:`OCRUnavailableError` instead of crashing elsewhere.

TODO: install system tesseract and `pip install pytesseract` to enable. Consider
a PaddleOCR adapter as an alternative (Task 3.3 lists both).
"""

from __future__ import annotations

from pathlib import Path

from app.models.schemas import BoundingBox, OCRPageResult, OCRToken


class OCRUnavailableError(RuntimeError):
    """Raised when the Tesseract engine or its Python binding is not installed."""


def _import_pytesseract():
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise OCRUnavailableError(
            "pytesseract is not installed. Run `pip install pytesseract` and "
            "install the system `tesseract` binary."
        ) from exc
    return pytesseract


class TesseractOCRProvider:
    name = "tesseract"

    def __init__(self, lang: str = "eng") -> None:
        self._lang = lang

    def is_available(self) -> bool:
        try:
            pytesseract = _import_pytesseract()
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def extract_page(self, image_path: Path, page_number: int) -> OCRPageResult:
        pytesseract = _import_pytesseract()
        from PIL import Image

        try:
            version = str(pytesseract.get_tesseract_version())
        except Exception as exc:  # pragma: no cover - environment dependent
            raise OCRUnavailableError(
                "The `tesseract` binary was not found on PATH."
            ) from exc

        with Image.open(image_path) as image:
            image = image.convert("RGB")
            text = pytesseract.image_to_string(image, lang=self._lang)
            data = pytesseract.image_to_data(
                image, lang=self._lang, output_type=pytesseract.Output.DICT
            )

        tokens: list[OCRToken] = []
        for word, conf, x, y, w, h in zip(
            data["text"],
            data["conf"],
            data["left"],
            data["top"],
            data["width"],
            data["height"],
            strict=True,
        ):
            if not word.strip():
                continue
            try:
                confidence = max(0.0, float(conf)) / 100.0
            except (TypeError, ValueError):
                confidence = 0.0
            tokens.append(
                OCRToken(
                    text=word,
                    confidence=min(1.0, confidence),
                    bbox=BoundingBox(x1=x, y1=y, x2=x + w, y2=y + h),
                )
            )

        return OCRPageResult(
            page=page_number,
            text=text.strip(),
            tokens=tokens,
            provider=self.name,
            provider_version=version,
        )
