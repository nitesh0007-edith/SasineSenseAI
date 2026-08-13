"""Local CSV-backed gazetteer place resolver (Phase 9).

Ambiguous names return *ranked* candidates rather than one forced answer. Ranking
is deterministic: exact name match > exact alias match > substring match, with
confidence reflecting match quality.

TODO: add a PostGIS-backed resolver (Task 9.3) for large gazetteers and spatial
queries. This CSV resolver is the local default.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.models.schemas import PlaceCandidate


@dataclass(frozen=True)
class GazetteerEntry:
    place_name: str
    aliases: tuple[str, ...]
    admin_area: str | None
    latitude: float | None
    longitude: float | None


def _parse_float(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


@lru_cache(maxsize=8)
def _load_entries(csv_path: str) -> tuple[GazetteerEntry, ...]:
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Gazetteer CSV not found: {path}")
    entries: list[GazetteerEntry] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            aliases = tuple(
                a.strip() for a in (row.get("aliases") or "").split(",") if a.strip()
            )
            entries.append(
                GazetteerEntry(
                    place_name=(row.get("place_name") or "").strip(),
                    aliases=aliases,
                    admin_area=(row.get("admin_area") or "").strip() or None,
                    latitude=_parse_float(row.get("latitude", "")),
                    longitude=_parse_float(row.get("longitude", "")),
                )
            )
    return tuple(entries)


class GazetteerPlaceResolver:
    name = "gazetteer"

    def __init__(self, csv_path: Path | str | None = None) -> None:
        self._csv_path = str(csv_path or settings.gazetteer_csv)

    def _to_candidate(self, entry: GazetteerEntry, confidence: float) -> PlaceCandidate:
        return PlaceCandidate(
            name=entry.place_name,
            normalized_name=entry.place_name,
            admin_area=entry.admin_area,
            latitude=entry.latitude,
            longitude=entry.longitude,
            confidence=confidence,
        )

    def resolve(self, place_name: str, *, limit: int = 5) -> list[PlaceCandidate]:
        query = (place_name or "").strip().casefold()
        if not query:
            return []

        entries = _load_entries(self._csv_path)
        scored: list[tuple[float, PlaceCandidate]] = []
        for entry in entries:
            name_cf = entry.place_name.casefold()
            aliases_cf = {a.casefold() for a in entry.aliases}
            if query == name_cf:
                score = 0.99
            elif query in aliases_cf:
                score = 0.90
            elif query in name_cf or any(query in a for a in aliases_cf):
                score = 0.60
            elif name_cf in query:
                score = 0.50
            else:
                continue
            scored.append((score, self._to_candidate(entry, score)))

        scored.sort(key=lambda item: (item[0], item[1].name), reverse=True)
        return [candidate for _, candidate in scored[:limit]]
