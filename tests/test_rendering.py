from pathlib import Path

import fitz
import pytest
from PIL import Image

from app.core.config import settings
from app.services.rendering import render_document


def create_one_page_pdf(path: Path) -> None:
    with fitz.open() as document:
        page = document.new_page(width=144, height=72)
        page.insert_text((20, 30), "Synthetic property record")
        document.save(path)


def test_render_one_page_pdf_returns_page_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "record.pdf"
    render_dir = tmp_path / "rendered"
    create_one_page_pdf(pdf_path)
    monkeypatch.setattr(settings, "render_dir", render_dir)

    pages = render_document(pdf_path, document_id="doc_test", dpi=72)

    assert len(pages) == 1
    page = pages[0]
    assert page.page_number == 1
    assert page.width == 144
    assert page.height == 72
    assert Path(page.local_image_path).is_file()


def test_render_pdf_uses_configured_dpi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "record.pdf"
    create_one_page_pdf(pdf_path)
    monkeypatch.setattr(settings, "render_dir", tmp_path / "rendered")
    monkeypatch.setattr(settings, "pdf_render_dpi", 144)

    page = render_document(pdf_path, document_id="doc_test")[0]

    assert page.width == 288
    assert page.height == 144


def test_render_image_returns_page_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = tmp_path / "record.png"
    Image.new("RGB", (80, 40), "white").save(image_path)
    monkeypatch.setattr(settings, "render_dir", tmp_path / "rendered")

    page = render_document(image_path, document_id="doc_test")[0]

    assert page.page_number == 1
    assert (page.width, page.height) == (80, 40)
    assert Path(page.local_image_path).is_file()


def test_render_document_rejects_invalid_dpi(tmp_path: Path) -> None:
    image_path = tmp_path / "record.png"
    Image.new("RGB", (80, 40), "white").save(image_path)

    with pytest.raises(ValueError, match="DPI must be greater than zero"):
        render_document(image_path, document_id="doc_test", dpi=0)
