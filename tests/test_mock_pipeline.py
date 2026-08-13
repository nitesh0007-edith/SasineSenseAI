from pathlib import Path

from PIL import Image

from app.services.pipeline import run_pipeline


def test_mock_pipeline(tmp_path: Path):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (500, 300), "white").save(image_path)

    result = run_pipeline("doc_test", str(image_path))

    assert result.document_id == "doc_test"
    assert result.document_type == "disposition"
    assert result.document_date is not None
    assert result.places
