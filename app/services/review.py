"""Append-only reviewer action log (Phase 10).

Reviewer decisions (accept / edit / flag / mark_unresolved) are recorded as an
immutable JSONL history per document. History is **never** deleted or rewritten:
edits append a new record capturing previous and new values, preserving the full
audit trail required for a non-authoritative, human-in-the-loop system.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.models.schemas import ReviewAction


class ReviewLog:
    """One append-only JSONL file per document under ``review_log_dir``."""

    def __init__(self, log_dir: Path | None = None) -> None:
        self._log_dir = Path(log_dir or settings.review_log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, document_id: str) -> Path:
        # Guard against path traversal from an untrusted document_id.
        safe = document_id.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self._log_dir / f"{safe}.jsonl"

    def append(self, action: ReviewAction) -> ReviewAction:
        path = self._path_for(action.document_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(action.model_dump_json() + "\n")
        return action

    def history(self, document_id: str) -> list[ReviewAction]:
        path = self._path_for(document_id)
        if not path.is_file():
            return []
        actions: list[ReviewAction] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    actions.append(ReviewAction.model_validate_json(line))
        return actions

    def latest_by_field(self, document_id: str) -> dict[str, ReviewAction]:
        """Most recent action per field (history itself is retained on disk)."""
        latest: dict[str, ReviewAction] = {}
        for action in self.history(document_id):
            latest[action.field] = action
        return latest
