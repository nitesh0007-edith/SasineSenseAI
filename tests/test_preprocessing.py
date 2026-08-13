from pathlib import Path

import numpy as np
from PIL import Image

from app.services.preprocessing import (
    PreprocessConfig,
    crop,
    deskew,
    preprocess_image,
    threshold,
    to_grayscale,
)


def _make_image(path: Path, size=(120, 80), color=(200, 200, 200)) -> None:
    img = Image.new("RGB", size, color)
    # Draw a dark bar so deskew/threshold have signal to work with.
    px = img.load()
    for x in range(20, 100):
        for y in range(30, 40):
            px[x, y] = (10, 10, 10)
    img.save(path)


def test_preprocess_noop_preserves_original(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    _make_image(image_path)
    cfg = PreprocessConfig(
        grayscale=False,
        normalize_contrast=False,
        deskew=False,
        denoise=False,
        threshold=False,
    )

    result = preprocess_image(image_path, config=cfg)

    assert result.operations == []
    assert result.processed_image_path == image_path
    assert result.metadata.get("noop") is True
    assert image_path.is_file()


def test_preprocess_basic_writes_derived_image(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    _make_image(image_path)
    cfg = PreprocessConfig(
        grayscale=True,
        normalize_contrast=True,
        deskew=True,
        denoise=False,
        threshold=True,
    )

    result = preprocess_image(image_path, config=cfg)

    assert result.processed_image_path != image_path
    assert result.processed_image_path.is_file()
    assert "grayscale" in result.operations
    assert "threshold" in result.operations
    assert "deskew_angle_deg" in result.metadata
    # Original untouched.
    assert Image.open(image_path).mode == "RGB"


def test_threshold_is_binary(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    _make_image(image_path)
    import cv2

    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    binary = threshold(img)
    assert set(np.unique(binary)).issubset({0, 255})


def test_to_grayscale_idempotent() -> None:
    gray = np.full((10, 10), 128, dtype=np.uint8)
    assert to_grayscale(gray).ndim == 2


def test_crop_validates_box() -> None:
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    cropped = crop(img, (10, 10, 40, 40))
    assert cropped.shape[:2] == (30, 30)


def test_deskew_returns_angle() -> None:
    img = np.full((60, 120, 3), 255, dtype=np.uint8)
    _, angle = deskew(img)
    assert isinstance(angle, float)
