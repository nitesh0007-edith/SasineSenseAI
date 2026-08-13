from pathlib import Path

from fastapi.testclient import TestClient

from app.db.repository import DocumentRepository
from app.models.schemas import (
    DocumentRecord,
    PropertyRecordExtraction,
    ReviewAction,
)


def _repo(tmp_path: Path) -> DocumentRepository:
    return DocumentRepository(database_url=f"sqlite:///{tmp_path/'t.db'}")


def test_document_roundtrip(tmp_path: Path):
    repo = _repo(tmp_path)
    record = DocumentRecord(
        document_id="doc_1", filename="a.pdf", media_type="application/pdf",
        size_bytes=10, local_path="/tmp/a.pdf",
    )
    repo.save_document(record)
    assert repo.get_document("doc_1").filename == "a.pdf"
    assert repo.get_document("missing") is None
    repo.close()


def test_save_document_idempotent(tmp_path: Path):
    repo = _repo(tmp_path)
    record = DocumentRecord(
        document_id="doc_1", filename="a.pdf", size_bytes=1, local_path="/tmp/a.pdf"
    )
    repo.save_document(record)
    repo.save_document(record)  # no duplicate / no error
    assert repo.get_document("doc_1") is not None
    repo.close()


def test_extraction_persisted_and_reloaded(tmp_path: Path):
    repo = _repo(tmp_path)
    repo.save_document(
        DocumentRecord(document_id="doc_1", filename="a.pdf", size_bytes=1,
                       local_path="/tmp/a.pdf")
    )
    extraction = PropertyRecordExtraction(
        document_id="doc_1", document_type="disposition", overall_confidence=0.9,
        review_required=False,
    )
    repo.save_extraction(extraction)
    loaded = repo.latest_extraction("doc_1")
    assert loaded is not None
    assert loaded.document_type == "disposition"
    assert loaded.overall_confidence == 0.9
    repo.close()


def test_reviews_are_append_only(tmp_path: Path):
    repo = _repo(tmp_path)
    repo.save_document(
        DocumentRecord(document_id="doc_1", filename="a.pdf", size_bytes=1,
                       local_path="/tmp/a.pdf")
    )
    repo.append_review(ReviewAction(document_id="doc_1", field="date", action="edit",
                                   new_value="x"))
    repo.append_review(ReviewAction(document_id="doc_1", field="date", action="accept"))
    history = repo.review_history("doc_1")
    assert [h.action for h in history] == ["edit", "accept"]
    repo.close()


def test_api_persists_extraction(tmp_path: Path, monkeypatch):
    from app.api import main as api_main
    from app.core.config import settings

    db_url = f"sqlite:///{tmp_path/'api.db'}"
    monkeypatch.setattr(api_main, "DATABASE_URL_OVERRIDE", db_url)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    api_main.DOCUMENTS.clear()

    client = TestClient(api_main.app)

    # Upload a tiny valid PNG so rendering + pipeline succeed.
    from PIL import Image

    img_path = tmp_path / "src.png"
    Image.new("RGB", (300, 200), "white").save(img_path)
    with img_path.open("rb") as fh:
        up = client.post("/documents", files={"file": ("src.png", fh.read(), "image/png")})
    assert up.status_code == 200
    doc_id = up.json()["document_id"]

    ext = client.post(f"/documents/{doc_id}/extract")
    assert ext.status_code == 200

    # Verify it landed in the database independently of the in-memory cache.
    repo = DocumentRepository(database_url=db_url)
    assert repo.get_document(doc_id) is not None
    assert repo.latest_extraction(doc_id) is not None
    repo.close()
