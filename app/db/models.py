"""ORM tables for documents, extractions and reviewer actions.

Extractions and review actions are stored as JSON payloads (the Pydantic schema
remains the source of truth) so the structured shape can evolve without brittle
column migrations, while still giving durable, queryable persistence. Review
actions are append-only rows — history is never updated in place.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.schemas import utc_now


class DocumentORM(Base):
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    media_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    local_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    extractions: Mapped[list[ExtractionORM]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[ReviewActionORM]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ExtractionORM(Base):
    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.document_id"))
    document_type: Mapped[str] = mapped_column(String(64))
    overall_confidence: Mapped[float] = mapped_column(default=0.0)
    review_required: Mapped[bool] = mapped_column(default=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    document: Mapped[DocumentORM] = relationship(back_populates="extractions")


class ReviewActionORM(Base):
    __tablename__ = "review_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.document_id"))
    field: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    document: Mapped[DocumentORM] = relationship(back_populates="reviews")
