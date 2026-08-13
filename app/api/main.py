from __future__ import annotations

import logging

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.db.repository import DocumentRepository
from app.models.schemas import DocumentRecord, PropertyRecordExtraction, ReviewAction
from app.services.ingestion import save_upload
from app.services.pipeline import run_pipeline
from app.services.review import ReviewLog

logger = logging.getLogger(__name__)

app = FastAPI(
    title="RoS Property Record Intelligence",
    version="0.1.0",
    description="Research prototype for AI-assisted property-record document understanding.",
)

# In-memory cache kept for fast lookups; the durable copy lives in the database.
DOCUMENTS: dict[str, DocumentRecord] = {}
REVIEW_LOG = ReviewLog()

# Tests can point persistence at a temporary database by setting this override.
DATABASE_URL_OVERRIDE: str | None = None


def get_repo() -> DocumentRepository:
    """A fresh repository/session per request (thread-safe for SQLite)."""
    return DocumentRepository(database_url=DATABASE_URL_OVERRIDE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/documents", response_model=DocumentRecord)
def upload_document(file: UploadFile = File(...)) -> DocumentRecord:
    try:
        record = save_upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    DOCUMENTS[record.document_id] = record
    repo = get_repo()
    try:
        repo.save_document(record)
    except Exception:  # persistence must not break ingestion
        logger.exception("Failed to persist document %s", record.document_id)
    finally:
        repo.close()
    return record


@app.post("/documents/{document_id}/extract", response_model=PropertyRecordExtraction)
def extract_document(document_id: str) -> PropertyRecordExtraction:
    repo = get_repo()
    try:
        record = DOCUMENTS.get(document_id) or repo.get_document(document_id)
        if not record:
            raise HTTPException(status_code=404, detail="Document not found")

        result = run_pipeline(document_id=document_id, local_path=record.local_path)
        try:
            repo.save_extraction(result)
        except Exception:
            logger.exception("Failed to persist extraction for %s", document_id)
        return result
    finally:
        repo.close()


@app.post("/documents/{document_id}/reviews", response_model=ReviewAction)
def add_review(document_id: str, action: ReviewAction) -> ReviewAction:
    if action.document_id != document_id:
        raise HTTPException(status_code=400, detail="document_id mismatch")
    REVIEW_LOG.append(action)  # append-only file log
    repo = get_repo()
    try:
        repo.append_review(action)  # durable append-only row
    except Exception:
        logger.exception("Failed to persist review for %s", document_id)
    finally:
        repo.close()
    return action


@app.get("/documents/{document_id}/reviews", response_model=list[ReviewAction])
def list_reviews(document_id: str) -> list[ReviewAction]:
    return REVIEW_LOG.history(document_id)
