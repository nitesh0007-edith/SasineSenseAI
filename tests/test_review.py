from pathlib import Path

from fastapi.testclient import TestClient

from app.models.schemas import ReviewAction
from app.services.review import ReviewLog


def test_review_log_appends_and_preserves_history(tmp_path: Path):
    log = ReviewLog(tmp_path)
    log.append(
        ReviewAction(
            document_id="doc_1", field="document_date", action="edit",
            previous_value="1876-05-12", new_value="1876-05-13", reviewer="alice",
        )
    )
    log.append(
        ReviewAction(
            document_id="doc_1", field="document_date", action="accept",
            previous_value="1876-05-13", new_value="1876-05-13", reviewer="bob",
        )
    )

    history = log.history("doc_1")
    assert len(history) == 2  # nothing overwritten
    assert history[0].action == "edit"
    assert history[1].action == "accept"
    # Latest-by-field reflects the most recent, but history is retained on disk.
    assert log.latest_by_field("doc_1")["document_date"].reviewer == "bob"


def test_review_log_path_traversal_guard(tmp_path: Path):
    log = ReviewLog(tmp_path)
    log.append(ReviewAction(document_id="../evil", field="f", action="flag"))
    # File is written inside the log dir, not the parent.
    assert not (tmp_path.parent / "evil.jsonl").exists()
    assert list(tmp_path.glob("*.jsonl"))


def test_review_api_roundtrip(tmp_path: Path, monkeypatch):
    from app.api import main as api_main

    monkeypatch.setattr(api_main, "REVIEW_LOG", ReviewLog(tmp_path))
    client = TestClient(api_main.app)

    payload = {
        "document_id": "doc_api",
        "field": "places",
        "action": "flag",
        "note": "ambiguous place",
    }
    resp = client.post("/documents/doc_api/reviews", json=payload)
    assert resp.status_code == 200

    listing = client.get("/documents/doc_api/reviews")
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["note"] == "ambiguous place"


def test_review_api_rejects_id_mismatch(tmp_path: Path, monkeypatch):
    from app.api import main as api_main

    monkeypatch.setattr(api_main, "REVIEW_LOG", ReviewLog(tmp_path))
    client = TestClient(api_main.app)

    resp = client.post(
        "/documents/doc_x/reviews",
        json={"document_id": "doc_y", "field": "f", "action": "accept"},
    )
    assert resp.status_code == 400
