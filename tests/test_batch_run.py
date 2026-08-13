from pathlib import Path

from PIL import Image

from app.batch.run import discover_documents, process_documents, stable_document_id


def test_batch_discovers_supported_documents(tmp_path: Path):
    (tmp_path / "nested").mkdir()
    Image.new("RGB", (40, 40), "white").save(tmp_path / "nested" / "record.png")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    paths = discover_documents(tmp_path)

    assert [path.name for path in paths] == ["record.png"]


def test_batch_writes_jsonl_and_stable_id(tmp_path: Path):
    image = tmp_path / "record.png"
    Image.new("RGB", (40, 40), "white").save(image)
    output = tmp_path / "out" / "results.jsonl"

    counts = process_documents([image], output_path=output, persist=False)

    assert counts == {"discovered": 1, "processed": 1, "failed": 0}
    assert stable_document_id(image).startswith("doc_batch_")
    line = output.read_text(encoding="utf-8").strip()
    assert '"status": "processed"' in line
    assert '"document_id": "doc_batch_' in line
