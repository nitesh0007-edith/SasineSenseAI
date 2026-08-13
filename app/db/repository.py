"""Repository functions bridging Pydantic schemas and the ORM.

Keeps SQLAlchemy out of the API/business layers: callers pass and receive
Pydantic models. A ``FunctionRegistry``-free, explicit function API keeps the
persistence surface small and testable.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_session, init_db
from app.db.models import DocumentORM, ExtractionORM, ReviewActionORM
from app.models.schemas import DocumentRecord, PropertyRecordExtraction, ReviewAction


class DocumentRepository:
    """Thin persistence facade. Owns a Session or one is injected for tests."""

    def __init__(self, session: Session | None = None, *, database_url: str | None = None):
        if session is None:
            init_db(database_url)
            session = get_session(database_url)
            self._owns_session = True
        else:
            self._owns_session = False
        self._session = session

    def close(self) -> None:
        if self._owns_session:
            self._session.close()

    # -- documents ---------------------------------------------------------
    def save_document(self, record: DocumentRecord) -> DocumentRecord:
        existing = self._session.get(DocumentORM, record.document_id)
        if existing is None:
            self._session.add(
                DocumentORM(
                    document_id=record.document_id,
                    filename=record.filename,
                    media_type=record.media_type,
                    size_bytes=record.size_bytes,
                    local_path=record.local_path,
                    created_at=record.created_at,
                )
            )
            self._session.commit()
        return record

    def get_document(self, document_id: str) -> DocumentRecord | None:
        row = self._session.get(DocumentORM, document_id)
        if row is None:
            return None
        return DocumentRecord(
            document_id=row.document_id,
            filename=row.filename,
            media_type=row.media_type,
            size_bytes=row.size_bytes,
            local_path=row.local_path,
            created_at=row.created_at,
        )

    # -- extractions -------------------------------------------------------
    def save_extraction(self, extraction: PropertyRecordExtraction) -> PropertyRecordExtraction:
        self._session.add(
            ExtractionORM(
                document_id=extraction.document_id,
                document_type=extraction.document_type,
                overall_confidence=extraction.overall_confidence,
                review_required=extraction.review_required,
                payload=extraction.model_dump(mode="json"),
            )
        )
        self._session.commit()
        return extraction

    def latest_extraction(self, document_id: str) -> PropertyRecordExtraction | None:
        stmt = (
            select(ExtractionORM)
            .where(ExtractionORM.document_id == document_id)
            .order_by(ExtractionORM.id.desc())
            .limit(1)
        )
        row = self._session.scalars(stmt).first()
        if row is None:
            return None
        return PropertyRecordExtraction.model_validate(row.payload)

    # -- reviews (append-only) --------------------------------------------
    def append_review(self, action: ReviewAction) -> ReviewAction:
        self._session.add(
            ReviewActionORM(
                document_id=action.document_id,
                field=action.field,
                action=action.action,
                payload=action.model_dump(mode="json"),
            )
        )
        self._session.commit()
        return action

    def review_history(self, document_id: str) -> list[ReviewAction]:
        stmt = (
            select(ReviewActionORM)
            .where(ReviewActionORM.document_id == document_id)
            .order_by(ReviewActionORM.id.asc())
        )
        return [ReviewAction.model_validate(r.payload) for r in self._session.scalars(stmt)]
