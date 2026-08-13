"""Image preprocessing utilities (Phase 2).

Deterministic OpenCV/Pillow operations that improve OCR legibility. The
original render is never mutated: a derived image is written next to it and a
:class:`PreprocessResult` records exactly which operations ran.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings
from app.models.schemas import PreprocessResult


@dataclass
class PreprocessConfig:
    """Toggle each operation. Defaults are read from application settings."""

    grayscale: bool = True
    normalize_contrast: bool = True
    deskew: bool = True
    denoise: bool = True
    threshold: bool = False
    crop: tuple[int, int, int, int] | None = None  # (x1, y1, x2, y2)

    @classmethod
    def from_settings(cls) -> PreprocessConfig:
        return cls(
            grayscale=settings.preprocess_grayscale,
            normalize_contrast=settings.preprocess_normalize_contrast,
            deskew=settings.preprocess_deskew,
            denoise=settings.preprocess_denoise,
            threshold=settings.preprocess_threshold,
        )

    def any_enabled(self) -> bool:
        return any(
            (
                self.grayscale,
                self.normalize_contrast,
                self.deskew,
                self.denoise,
                self.threshold,
                self.crop is not None,
            )
        )


def to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def normalize_contrast(image: np.ndarray) -> np.ndarray:
    """CLAHE contrast normalization; falls back to global equalization on colour."""
    if image.ndim == 2:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(image)
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)


def estimate_skew_angle(gray: np.ndarray) -> float:
    """Estimate page skew in degrees using the minimum-area box of dark pixels."""
    inverted = cv2.bitwise_not(gray)
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    coords = cv2.findNonZero(binary)
    if coords is None or len(coords) < 10:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    return float(angle)


def deskew(image: np.ndarray) -> tuple[np.ndarray, float]:
    gray = to_grayscale(image)
    angle = estimate_skew_angle(gray)
    if abs(angle) < 0.1:
        return image, 0.0
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    border = cv2.BORDER_REPLICATE
    rotated = cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=border)
    return rotated, angle


def denoise(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.fastNlMeansDenoising(image, h=10)
    return cv2.fastNlMeansDenoisingColored(image, h=10)


def threshold(image: np.ndarray) -> np.ndarray:
    gray = to_grayscale(image)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return binary


def crop(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = box
    h, w = image.shape[:2]
    x1, x2 = max(0, x1), min(w, x2)
    y1, y2 = max(0, y1), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid crop box {box} for image of size {(w, h)}")
    return image[y1:y2, x1:x2]


def preprocess_image(
    image_path: Path,
    *,
    config: PreprocessConfig | None = None,
    output_path: Path | None = None,
) -> PreprocessResult:
    """Apply the configured operations and write a derived image.

    When nothing is enabled this is a no-op: ``processed_image_path`` equals the
    input and ``operations`` is empty (still non-destructive).
    """
    cfg = config or PreprocessConfig.from_settings()
    image_path = Path(image_path)

    if not cfg.any_enabled():
        return PreprocessResult(
            original_image_path=image_path,
            processed_image_path=image_path,
            operations=[],
            metadata={"noop": True},
        )

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    operations: list[str] = []
    metadata: dict[str, object] = {}

    if cfg.crop is not None:
        image = crop(image, cfg.crop)
        operations.append("crop")
        metadata["crop_box"] = list(cfg.crop)
    if cfg.grayscale:
        image = to_grayscale(image)
        operations.append("grayscale")
    if cfg.normalize_contrast:
        image = normalize_contrast(image)
        operations.append("normalize_contrast")
    if cfg.deskew:
        image, angle = deskew(image)
        operations.append("deskew")
        metadata["deskew_angle_deg"] = round(angle, 3)
    if cfg.denoise:
        image = denoise(image)
        operations.append("denoise")
    if cfg.threshold:
        image = threshold(image)
        operations.append("threshold")

    if output_path is None:
        output_path = image_path.with_name(f"{image_path.stem}_pre{image_path.suffix}")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)

    return PreprocessResult(
        original_image_path=image_path,
        processed_image_path=output_path,
        operations=operations,
        metadata=metadata,
    )
