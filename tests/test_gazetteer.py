from pathlib import Path

from app.providers.gazetteer import GazetteerPlaceResolver

CSV = """place_name,aliases,admin_area,latitude,longitude
Glasgow,"Glasgow City","Glasgow City",55.8642,-4.2518
Perth,"Perthshire","Perth and Kinross",56.3950,-3.4308
Perth Cross,"","Perth and Kinross",56.3960,-3.4300
"""


def _resolver(tmp_path: Path) -> GazetteerPlaceResolver:
    csv_path = tmp_path / "gaz.csv"
    csv_path.write_text(CSV, encoding="utf-8")
    return GazetteerPlaceResolver(csv_path)


def test_exact_match_ranks_first(tmp_path: Path):
    resolver = _resolver(tmp_path)
    results = resolver.resolve("Glasgow")
    assert results
    assert results[0].name == "Glasgow"
    assert results[0].confidence >= 0.99
    assert results[0].latitude == 55.8642


def test_alias_match(tmp_path: Path):
    resolver = _resolver(tmp_path)
    results = resolver.resolve("Perthshire")
    assert results[0].name == "Perth"


def test_ambiguous_returns_ranked_candidates(tmp_path: Path):
    resolver = _resolver(tmp_path)
    results = resolver.resolve("Perth")
    # Exact "Perth" plus substring "Perth Cross" — both returned, exact first.
    names = [r.name for r in results]
    assert names[0] == "Perth"
    assert "Perth Cross" in names
    assert results[0].confidence > results[1].confidence


def test_no_match_returns_empty(tmp_path: Path):
    resolver = _resolver(tmp_path)
    assert resolver.resolve("Atlantis") == []


def test_empty_query(tmp_path: Path):
    resolver = _resolver(tmp_path)
    assert resolver.resolve("") == []


def test_bundled_sample_csv_loads():
    # The committed sample gazetteer should be readable via the default path.
    resolver = GazetteerPlaceResolver()
    results = resolver.resolve("Edinburgh")
    assert results and results[0].name == "Edinburgh"
