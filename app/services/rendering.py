from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image

from app.core.config import settings
from app.models.schemas import RenderedPage

RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def render_document(
    path: Path,
    document_id: str,
    *,
    dpi: int | None = None,
) -> list[RenderedPage]:
    suffix = path.suffix.lower()
    render_dpi = settings.pdf_render_dpi if dpi is None else dpi
    if render_dpi <= 0:
        raise ValueError("DPI must be greater than zero")

    out_dir = settings.render_dir / document_id
    out_dir.mkdir(parents=True, exist_ok=True)

    if suffix == ".pdf":
        pages: list[RenderedPage] = []
        zoom = render_dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        with fitz.open(path) as document:
            for index, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                output_path = out_dir / f"page_{index:04d}.png"
                pixmap.save(output_path)
                pages.append(
                    RenderedPage(
                        page_number=index,
                        width=pixmap.width,
                        height=pixmap.height,
                        local_image_path=str(output_path),
                    )
                )
        return pages

    if suffix not in RASTER_SUFFIXES:
        raise ValueError(f"Unsupported file type for rendering: {suffix or 'unknown'}")

    pages = []
    with Image.open(path) as image:
        for index in range(1, getattr(image, "n_frames", 1) + 1):
            image.seek(index - 1)
            rgb_image = image.convert("RGB")
            output_path = out_dir / f"page_{index:04d}.png"
            rgb_image.save(output_path)
            width, height = rgb_image.size
            pages.append(
                RenderedPage(
                    page_number=index,
                    width=width,
                    height=height,
                    local_image_path=str(output_path),
                )
            )
    return pages
