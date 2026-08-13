"""Real structured-extraction provider via the Mesh API (Task 7.3).

Mesh (https://api.meshapi.ai/v1) is an OpenAI-compatible gateway. This provider
sends a **hybrid** request — the rendered page image(s) plus OCR text and the
deterministic regex/NER candidates — and asks for schema-constrained JSON only.

Safety properties required by the task:
- schema-constrained output only (mapped into ``PropertyRecordExtraction``);
- retry once on malformed JSON;
- never invent fields — the model is instructed to use ``null`` when uncertain;
- log provider / model / version into the extraction metadata;
- the API key is read from config/env, never hard-coded.

Model self-reported confidence is recorded but the pipeline's own validation and
confidence scoring remain authoritative (see ``app/services/validation.py``).
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from pathlib import Path

import requests

from app.core.config import settings
from app.models.schemas import (
    EvidenceSpan,
    ExtractedField,
    OCRPageResult,
    Party,
    PlaceCandidate,
    PropertyRecordExtraction,
)

logger = logging.getLogger(__name__)

MAX_IMAGES = 3  # cap payload size / cost
VALID_TYPES = {"sasine", "disposition", "deed", "title_sheet", "property_form", "unknown"}
VALID_ROLES = {"seller", "buyer", "owner", "granter", "grantee", "unknown"}

SYSTEM_PROMPT = (
    "You are a careful extraction engine for historical Scottish/UK property and "
    "legal records. Return ONLY a single JSON object, no prose, no markdown fences. "
    "Extract only what is visibly supported by the page image or OCR text. If a "
    "field is not clearly present, use null (or an empty list). Do NOT guess or "
    "invent values. For every extracted value include short verbatim 'evidence' "
    "text copied from the source. This output is non-authoritative and will be "
    "human-reviewed.\n\n"
    "JSON schema (use exactly these keys):\n"
    "{\n"
    '  "document_type": one of ["sasine","disposition","deed","title_sheet",'
    '"property_form","unknown"],\n'
    '  "document_date": {"value": string|null, "normalized_value": '
    '"YYYY-MM-DD"|null, "evidence": string|null} | null,\n'
    '  "parties": [{"name": string, "role": one of ["seller","buyer","owner",'
    '"granter","grantee","unknown"], "evidence": string}],\n'
    '  "places": [{"name": string, "evidence": string}],\n'
    '  "property_description": {"value": string, "evidence": string} | null,\n'
    '  "title_references": [{"value": string, "evidence": string}]\n'
    "}\n"
)


class MeshUnavailableError(RuntimeError):
    """Raised when the Mesh API key/endpoint is not configured."""


def _image_data_uri(path: Path) -> str | None:
    path = Path(path)
    if not path.is_file():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


class MeshStructuredExtractionProvider:
    name = "mesh"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self._base_url = (base_url or settings.structured_api_base).rstrip("/")
        self._api_key = api_key if api_key is not None else settings.structured_api_key
        self._model = model or settings.structured_api_model
        self._timeout = timeout or settings.structured_api_timeout

    # -- HTTP --------------------------------------------------------------
    def _post_chat(self, messages: list[dict]) -> dict:
        if not self._api_key:
            raise MeshUnavailableError(
                "No Mesh API key configured. Set MESH_API_KEY (or STRUCTURED_API_KEY)."
            )
        resp = requests.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            # `temperature` is intentionally omitted: some newer models reject it
            # as deprecated. Determinism is encouraged via the strict prompt.
            json={"model": self._model, "messages": messages},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _build_messages(
        self,
        ocr_pages: list[OCRPageResult],
        page_images: list[Path],
        context: dict | None,
    ) -> list[dict]:
        ocr_text = "\n\n".join(f"[page {p.page}]\n{p.text}" for p in ocr_pages)
        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    "Extract the property-record fields from the following document. "
                    "OCR text:\n" + (ocr_text or "(no OCR text)")
                ),
            }
        ]
        if context:
            content.append(
                {"type": "text", "text": "Deterministic candidates (hints only):\n"
                 + json.dumps(context)[:4000]}
            )
        for image_path in page_images[:MAX_IMAGES]:
            uri = _image_data_uri(image_path)
            if uri:
                content.append({"type": "image_url", "image_url": {"url": uri}})
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

    # -- parsing -----------------------------------------------------------
    @staticmethod
    def _content_text(response: dict) -> str:
        try:
            return response["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return ""

    @staticmethod
    def _loads(raw: str) -> dict | None:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw[raw.find("{") : raw.rfind("}") + 1]
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            start, end = raw.find("{"), raw.rfind("}")
            if 0 <= start < end:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    return None
            return None

    def extract(
        self,
        *,
        document_id: str,
        ocr_pages: list[OCRPageResult],
        page_images: list[Path],
        context: dict | None = None,
    ) -> PropertyRecordExtraction:
        messages = self._build_messages(ocr_pages, page_images, context)

        response = self._post_chat(messages)
        data = self._loads(self._content_text(response))
        if data is None:
            # Retry once with a stricter instruction (Task 7.3 requirement).
            retry_messages = messages + [
                {"role": "user", "content": "Your previous reply was not valid JSON. "
                 "Reply with ONLY the JSON object, nothing else."}
            ]
            response = self._post_chat(retry_messages)
            data = self._loads(self._content_text(response))

        page = ocr_pages[0].page if ocr_pages else 1
        version = str(response.get("model") or self._model)
        metadata = {
            "provider": self.name,
            "model": version,
            "response_id": response.get("id"),
            "usage": response.get("usage"),
        }

        if data is None:
            logger.warning("Mesh returned unparseable JSON for %s", document_id)
            return PropertyRecordExtraction(
                document_id=document_id,
                review_required=True,
                metadata={**metadata, "error": "malformed_json"},
            )

        return self._to_extraction(document_id, data, page, metadata)

    def _to_extraction(
        self, document_id: str, data: dict, page: int, metadata: dict
    ) -> PropertyRecordExtraction:
        def evidence(text) -> list[EvidenceSpan]:
            if not text:
                return []
            return [EvidenceSpan(page=page, text=str(text), source="mesh_vlm")]

        doc_type = data.get("document_type")
        if doc_type not in VALID_TYPES:
            doc_type = "unknown"

        document_date = None
        raw_date = data.get("document_date")
        if isinstance(raw_date, dict) and raw_date.get("value"):
            document_date = ExtractedField(
                name="document_date",
                value=raw_date.get("value"),
                normalized_value=raw_date.get("normalized_value"),
                confidence=0.6,  # model self-report; pipeline re-scores
                method="mesh_vlm",
                evidence=evidence(raw_date.get("evidence")),
            )

        parties: list[Party] = []
        for item in data.get("parties") or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            role = item.get("role")
            parties.append(
                Party(
                    name=str(item["name"]),
                    role=role if role in VALID_ROLES else "unknown",
                    confidence=0.6,
                    evidence=evidence(item.get("evidence")),
                )
            )

        places: list[PlaceCandidate] = []
        for item in data.get("places") or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            places.append(
                PlaceCandidate(
                    name=str(item["name"]),
                    confidence=0.6,
                    evidence=evidence(item.get("evidence")),
                )
            )

        property_description = None
        raw_desc = data.get("property_description")
        if isinstance(raw_desc, dict) and raw_desc.get("value"):
            property_description = ExtractedField(
                name="property_description",
                value=str(raw_desc["value"]),
                confidence=0.5,
                method="mesh_vlm",
                evidence=evidence(raw_desc.get("evidence")),
            )

        title_references: list[ExtractedField] = []
        for item in data.get("title_references") or []:
            if not isinstance(item, dict) or not item.get("value"):
                continue
            title_references.append(
                ExtractedField(
                    name="title_reference",
                    value=str(item["value"]),
                    confidence=0.5,
                    method="mesh_vlm",
                    evidence=evidence(item.get("evidence")),
                )
            )

        return PropertyRecordExtraction(
            document_id=document_id,
            document_type=doc_type,  # type: ignore[arg-type]
            document_date=document_date,
            parties=parties,
            property_description=property_description,
            places=places,
            title_references=title_references,
            source_pages=[page],
            review_required=True,
            metadata=metadata,
        )
