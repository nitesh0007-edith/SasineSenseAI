from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.api.main import DOCUMENTS, app
from app.core.config import settings
from app.services.ingestion import save_upload


def make_upload(filename: str, content: bytes = b"test content") -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=filename)


@pytest.mark.parametrize("suffix", [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"])
def test_save_upload_accepts_supported_extensions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    record = save_upload(make_upload(f"record{suffix}"))

    assert record.document_id.startswith("doc_")
    assert len(record.document_id.removeprefix("doc_")) == 32
    assert record.filename == f"record{suffix}"
    assert record.size_bytes == len(b"test content")
    assert Path(record.local_path).read_bytes() == b"test content"


def test_save_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported file type"):
        save_upload(make_upload("record.txt"))

    assert not list(tmp_path.iterdir())


def test_save_upload_rejects_empty_file() -> None:
    with pytest.raises(ValueError, match="File is empty"):
        save_upload(make_upload("record.pdf", b""))


def test_save_upload_rejects_file_over_size_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    oversized_content = b"x" * (1024 * 1024 + 1)

    with pytest.raises(ValueError, match="File exceeds 1 MB limit"):
        save_upload(make_upload("record.pdf", oversized_content))


def test_post_documents_stores_metadata_in_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    DOCUMENTS.clear()
    client = TestClient(app)

    response = client.post(
        "/documents",
        files={"file": ("record.pdf", b"pdf bytes", "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] in DOCUMENTS
    assert DOCUMENTS[body["document_id"]].filename == "record.pdf"


def test_post_documents_rejects_invalid_input() -> None:
    client = TestClient(app)

    response = client.post(
        "/documents",
        files={"file": ("record.txt", b"text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type: .txt"
