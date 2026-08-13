import json
from pathlib import Path

import pytest
from PIL import Image

from app.models.schemas import OCRPageResult
from app.providers.mesh_structured import (
    MeshStructuredExtractionProvider,
    MeshUnavailableError,
)


def _pages():
    return [OCRPageResult(page=1, text="Disposition by John Campbell.", provider="mock")]


def _image(tmp_path: Path) -> Path:
    p = tmp_path / "page.png"
    Image.new("RGB", (50, 50), "white").save(p)
    return p


def _fake_response(content: str, model="anthropic/claude-3-5-sonnet"):
    return {
        "id": "resp_1",
        "model": model,
        "usage": {"total_tokens": 10},
        "choices": [{"message": {"role": "assistant", "content": content}}],
    }


GOOD_JSON = json.dumps(
    {
        "document_type": "disposition",
        "document_date": {"value": "12 May 1876", "normalized_value": "1876-05-12",
                          "evidence": "dated 12 May 1876"},
        "parties": [{"name": "John Campbell", "role": "granter",
                     "evidence": "by John Campbell"}],
        "places": [{"name": "Glasgow", "evidence": "in Glasgow"}],
        "property_description": None,
        "title_references": [],
    }
)


def test_missing_key_raises(tmp_path: Path):
    provider = MeshStructuredExtractionProvider(api_key="")
    with pytest.raises(MeshUnavailableError):
        provider.extract(document_id="d1", ocr_pages=_pages(),
                         page_images=[_image(tmp_path)])


def test_parses_schema_constrained_json(tmp_path: Path, monkeypatch):
    provider = MeshStructuredExtractionProvider(api_key="rsk_test")

    calls = {"n": 0}

    def fake_post(*args, **kwargs):
        calls["n"] += 1

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return _fake_response(GOOD_JSON)

        return R()

    monkeypatch.setattr("app.providers.mesh_structured.requests.post", fake_post)

    result = provider.extract(document_id="d1", ocr_pages=_pages(),
                              page_images=[_image(tmp_path)])
    assert calls["n"] == 1  # no retry needed
    assert result.document_type == "disposition"
    assert result.document_date.normalized_value == "1876-05-12"
    assert result.parties[0].name == "John Campbell"
    assert result.parties[0].role == "granter"
    assert result.parties[0].evidence  # evidence preserved
    assert result.places[0].name == "Glasgow"
    assert result.metadata["provider"] == "mesh"
    assert result.metadata["model"] == "anthropic/claude-3-5-sonnet"


def test_retries_once_on_malformed_json(tmp_path: Path, monkeypatch):
    provider = MeshStructuredExtractionProvider(api_key="rsk_test")
    responses = [_fake_response("not json at all"), _fake_response(GOOD_JSON)]

    def fake_post(*args, **kwargs):
        payload = responses.pop(0)

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return payload

        return R()

    monkeypatch.setattr("app.providers.mesh_structured.requests.post", fake_post)

    result = provider.extract(document_id="d1", ocr_pages=_pages(),
                              page_images=[_image(tmp_path)])
    assert not responses  # both responses consumed -> retried exactly once
    assert result.document_type == "disposition"


def test_still_malformed_after_retry_flags_review(tmp_path: Path, monkeypatch):
    provider = MeshStructuredExtractionProvider(api_key="rsk_test")

    def fake_post(*args, **kwargs):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return _fake_response("garbage")

        return R()

    monkeypatch.setattr("app.providers.mesh_structured.requests.post", fake_post)

    result = provider.extract(document_id="d1", ocr_pages=_pages(),
                              page_images=[_image(tmp_path)])
    assert result.review_required is True
    assert result.metadata.get("error") == "malformed_json"


def test_does_not_invent_uncertain_fields(tmp_path: Path, monkeypatch):
    provider = MeshStructuredExtractionProvider(api_key="rsk_test")
    sparse = json.dumps({"document_type": "unknown", "document_date": None,
                         "parties": [], "places": []})

    def fake_post(*args, **kwargs):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return _fake_response(sparse)

        return R()

    monkeypatch.setattr("app.providers.mesh_structured.requests.post", fake_post)

    result = provider.extract(document_id="d1", ocr_pages=_pages(),
                              page_images=[_image(tmp_path)])
    assert result.document_date is None  # null preserved, not fabricated
    assert result.parties == []
    assert result.places == []
