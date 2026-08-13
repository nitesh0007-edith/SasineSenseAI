from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.models.schemas import DocumentRecord

ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def save_upload(upload: UploadFile) -> DocumentRecord:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    raw = upload.file.read(max_bytes + 1)
    if not raw:
        raise ValueError("File is empty")
    if len(raw) > max_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit")

    document_id = f"doc_{uuid.uuid4().hex}"
    dest = settings.upload_dir / f"{document_id}{suffix}"
    dest.write_bytes(raw)

    return DocumentRecord(
        document_id=document_id,
        filename=upload.filename or dest.name,
        media_type=upload.content_type,
        size_bytes=len(raw),
        local_path=str(dest),
    )
