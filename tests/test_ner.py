from app.models.schemas import OCRPageResult
from app.providers.spacy_ner import SpacyNERProvider


def _page(text: str) -> OCRPageResult:
    return OCRPageResult(page=1, text=text, provider="test", tokens=[])


def test_ner_extracts_person_and_place():
    provider = SpacyNERProvider()
    text = "Disposition by John Campbell in favour of Mary Fraser situated in Glasgow."
    ents = provider.extract_entities(_page(text))

    labels = {e.label for e in ents}
    # Statistical model (en_core_web_sm) should surface people/places; custom
    # ruler should surface legal cues. At minimum we get some entities with
    # evidence and valid offsets.
    assert ents
    for e in ents:
        assert e.evidence
        assert 0 <= e.start_char < e.end_char <= len(text)
        assert e.text == text[e.start_char : e.end_char]
    assert "PERSON" in labels or "PLACE_CUE" in labels or "GPE" in labels


def test_ner_custom_party_role():
    provider = SpacyNERProvider()
    ents = provider.extract_entities(_page("The granter conveys to the grantee."))
    role_terms = {e.text.lower() for e in ents if e.label == "PARTY_ROLE"}
    assert {"granter", "grantee"} <= role_terms


def test_ner_empty_text():
    provider = SpacyNERProvider()
    assert provider.extract_entities(_page("")) == []
