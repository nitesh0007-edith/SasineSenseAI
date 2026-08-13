# Codex Task Plan

This file is intentionally explicit so Codex can work incrementally.

## Ground rules

- Keep each change small and testable.
- Do not invent production RoS APIs or internal systems.
- Use interfaces/adapters for external OCR/VLM providers.
- Default to local/mock implementations.
- Every extracted field should be traceable to evidence.
- Never silently overwrite an extracted value.
- Never auto-accept low-confidence legal-property fields.
- Add tests with every feature.
- Prefer deterministic parsing before adding LLM complexity.

---

# Phase 0 — repository health

## Task 0.1
Verify package imports and test suite.

Acceptance:
- `pytest` runs.
- `uvicorn app.api.main:app --reload` starts.
- `/health` returns `{"status":"ok"}`.

## Task 0.2
Add pre-commit-friendly formatting/linting configuration.

Acceptance:
- ruff configuration present.
- no obvious import/style errors.

---

# Phase 1 — ingestion

## Task 1.1
Implement document ingestion.

Requirements:
- accept PDF, PNG, JPG/JPEG, TIFF;
- validate size and extension;
- assign stable UUID;
- create `DocumentRecord`;
- store metadata only in-memory initially.

Acceptance:
- unit tests for valid and invalid inputs;
- API endpoint `POST /documents`.

## Task 1.2
Implement PDF-to-page-image rendering.

Requirements:
- use PyMuPDF;
- return page objects with page number, width, height, local image path;
- configurable DPI.

Acceptance:
- test with generated one-page PDF.

---

# Phase 2 — preprocessing

## Task 2.1
Implement image preprocessing utilities:
- grayscale
- contrast normalization
- deskew
- denoise
- thresholding
- optional crop

Important:
- preserve original image;
- output preprocessing metadata.

Acceptance:
- preprocessing pipeline can be toggled by config;
- tests cover no-op and basic processing.

---

# Phase 3 — OCR

## Task 3.1
Create `OCRProvider` protocol/interface.

Return:
- page text
- token/word text
- bbox
- confidence
- provider metadata

## Task 3.2
Implement `MockOCRProvider`.

Use deterministic test data.

## Task 3.3
Implement first real provider.

Preferred first:
- Tesseract adapter if available locally;
or
- PaddleOCR adapter if installation is stable.

Do not hard-wire provider into business logic.

Acceptance:
- provider selected by env/config;
- OCR output stored as `OCRPageResult`.

---

# Phase 4 — regex baseline

## Task 4.1
Create rule-based extraction.

Start fields:
- dates
- likely title references
- page/reference numbers
- money values
- postcodes
- obvious deed keywords

## Task 4.2
Create document-type keyword classifier.

Initial labels:
- sasine
- disposition
- deed
- title_sheet
- property_form
- unknown

Use deterministic rules first.

Acceptance:
- tests using text fixtures.

---

# Phase 5 — spaCy

## Task 5.1
Create `NERProvider` interface.

## Task 5.2
Implement spaCy adapter.

Extract:
- PERSON
- ORG
- GPE/LOC
- DATE

## Task 5.3
Add custom `EntityRuler` patterns for:
- Scottish legal/deed terms
- "lands of ..."
- "situated at/in ..."
- county/parish markers
- party-role indicators

Acceptance:
- return normalized entity candidates with evidence spans.

---

# Phase 6 — structured extraction schema

## Task 6.1
Implement Pydantic models:
- EvidenceSpan
- ExtractedField
- Party
- PlaceCandidate
- PropertyRecordExtraction
- ValidationResult

## Task 6.2
Create merge strategy.

Rules:
- preserve all candidates;
- record method;
- score agreements;
- never discard conflicting candidates silently.

---

# Phase 7 — VLM/LLM adapter

## Task 7.1
Create `StructuredExtractionProvider` interface.

Input:
- page images
- OCR text
- regex candidates
- NER candidates

Output:
- schema-constrained extraction only.

## Task 7.2
Implement `MockStructuredExtractionProvider`.

## Task 7.3
Add one real provider only after mock integration passes.

Provider must:
- return JSON only;
- include evidence text where possible;
- not invent missing fields;
- use `null` if uncertain.

Acceptance:
- schema validation;
- retry once on malformed JSON;
- log model/provider/version.

---

# Phase 8 — validation and confidence

## Task 8.1
Implement validation rules.

Examples:
- date parseable
- title/reference pattern valid
- place non-empty
- evidence contains or closely matches extracted value
- party names not identical to known boilerplate
- fields supported by source page

## Task 8.2
Implement confidence score.

Initial simple formula:
- OCR confidence
- source agreement
- validation status
- evidence support
- model confidence if available

Do not treat LLM self-reported confidence as sufficient.

## Task 8.3
Implement review-routing thresholds.

Example config:
- >= 0.90: high confidence candidate
- 0.70–0.89: quick review
- < 0.70: manual review

All remain non-authoritative.

---

# Phase 9 — place resolution

## Task 9.1
Create `PlaceResolver` interface.

## Task 9.2
Implement local gazetteer resolver.

Start with CSV fixture:
- place_name
- aliases
- admin_area
- latitude
- longitude

## Task 9.3
Add PostGIS-backed implementation later.

Acceptance:
- ambiguous places return ranked candidates, not one forced answer.

---

# Phase 10 — reviewer UI

## Task 10.1
Streamlit document viewer.

Display:
- page image
- OCR text
- extracted fields
- confidence
- evidence
- validation flags

## Task 10.2
Reviewer actions:
- accept
- edit
- flag
- mark unresolved

Store action with:
- timestamp
- document_id
- field
- previous value
- new value
- reviewer action type

Do not delete history.

---

# Phase 11 — evaluation harness

## Task 11.1
Define annotation JSONL format.

## Task 11.2
Implement metrics:
- exact match
- field P/R/F1
- CER
- WER
- unsupported extraction rate
- review rate

## Task 11.3
Implement baseline comparison report.

Generate CSV and markdown summary.

---

# Phase 12 — bounded agents

Only begin after Phases 1–11 work.

Implement as orchestrated tools, not autonomous free-form agents.

## Agent A: Triage
Allowed:
- classify document
- choose OCR/HTR path
Not allowed:
- modify extracted data

## Agent B: Verification
Allowed:
- compare field candidates with evidence
- emit pass/fail/uncertain
Not allowed:
- invent replacement values

## Agent C: Consistency
Allowed:
- compare multiple documents
- flag conflicts
Not allowed:
- decide legal ownership

## Agent D: Geo resolution
Allowed:
- query place resolver
- rank candidates
Not allowed:
- overwrite property location without review

Every agent action:
- logged;
- schema-constrained;
- deterministic tool permissions;
- reviewable.

---

# First milestone definition

The first demo is complete when a user can:

1. upload a PDF/image;
2. see its rendered page;
3. run OCR;
4. extract at least dates, persons and places;
5. get a structured `PropertyRecordExtraction`;
6. see confidence/evidence;
7. review/edit results in Streamlit.

Do not add agents before this milestone.
