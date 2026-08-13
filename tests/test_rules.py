from app.models.schemas import OCRPageResult
from app.services.rules import (
    classify_document_type,
    classify_document_type_scores,
    extract_all,
    extract_dates,
    extract_deed_keywords,
    extract_money,
    extract_postcodes,
    extract_property_description,
    extract_proprietor,
    extract_reference_numbers,
    extract_title_references,
    extract_title_sheet_dates,
)


def _page(text: str) -> OCRPageResult:
    return OCRPageResult(page=1, text=text, provider="test", tokens=[])


def test_document_type_disposition():
    text = "This Disposition is made between..."
    assert classify_document_type(text) == "disposition"


def test_document_type_scored_picks_strongest():
    # Mentions both "deed" and "instrument of sasine"; sasine cue is stronger.
    text = "This deed, being an instrument of sasine, is recorded."
    scores = classify_document_type_scores(text)
    assert scores["sasine"] > scores["deed"]
    assert classify_document_type(text) == "sasine"


def test_document_type_unknown():
    assert classify_document_type("nothing relevant here") == "unknown"


def test_extract_date():
    dates = extract_dates(_page("Disposition dated 12 May 1876."))
    assert len(dates) == 1
    assert dates[0].normalized_value == "1876-05-12"


def test_extract_money():
    fields = extract_money(_page("consideration of £1,250.00 sterling"))
    assert fields
    assert fields[0].value.startswith("£")


def test_extract_postcode():
    fields = extract_postcodes(_page("situated at 5 High Street, Glasgow G1 1AA"))
    assert any("G1 1AA".replace(" ", "") in f.value.replace(" ", "") for f in fields)


def test_extract_title_reference():
    fields = extract_title_references(_page("registered under title number GLA123456"))
    assert any(f.value.upper() == "GLA123456" for f in fields)


def test_extract_reference_number():
    fields = extract_reference_numbers(_page("See Page 42 of the register"))
    assert fields
    assert fields[0].value == "42"


def test_extract_deed_keywords():
    fields = extract_deed_keywords(_page("granter John in favour of grantee Mary"))
    values = {f.value for f in fields}
    assert {"granter", "grantee", "in favour of"} <= values


def test_extract_all_keys():
    result = extract_all(_page("Disposition dated 12 May 1876 for £500 GLA123456"))
    assert set(result) == {
        "dates",
        "money",
        "postcodes",
        "title_references",
        "reference_numbers",
        "deed_keywords",
    }


def test_title_sheet_labelled_fields():
    page = _page(
        "Date of First Registration: 13/02/2008\n"
        "Description:\nSubjects FLAT 2 at 27 CASTLE TERRACE, EDINBURGH EH1 2EL\n"
        "B. PROPRIETORSHIP SECTION\nD&T LYNCH INVESTMENTS PTY LTD\nNotes:"
    )
    dates = extract_title_sheet_dates(page)
    description = extract_property_description(page)
    proprietor = extract_proprietor(page)

    assert dates[0].normalized_value == "2008-02-13"
    assert "CASTLE TERRACE" in description.value
    assert proprietor.value == "D&T LYNCH INVESTMENTS PTY LTD"
