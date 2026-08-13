<div align="center">

# SasineSense AI

### Evidence-first document intelligence for historical Scottish property records

<p>
  <img src="https://img.shields.io/badge/tests-85%20passed-16a085?logo=pytest" alt="85 tests passed">
  <img src="https://img.shields.io/badge/lint-ruff%20clean-4c9a2b" alt="Ruff clean">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776ab?logo=python&logoColor=white" alt="Python 3.11 or newer">
  <img src="https://img.shields.io/badge/status-research%20prototype-orange" alt="Research prototype">
</p>

Scanned deeds, sasines, dispositions, title-related forms and maps are difficult to search, compare and validate. SasineSense AI combines deterministic extraction, NLP, OCR, vision-language models and human review into one provenance-preserving pipeline.

<p><a href="#quick-start">Quick start</a> · <a href="#architecture">Architecture</a> · <a href="#api">API</a> · <a href="#roadmap">Roadmap</a></p>

</div>

> **Safety notice:** This is a research demonstrator using public or synthetic documents. It is not an authoritative land-registration system and must not be used to make legal title decisions. Low-confidence and conflicting values are routed to a reviewer.

![SasineSense AI architecture](docs/architecture.svg)

## Why this project

Historical property records mix inconsistent typography, archaic language, scanned images, handwritten notes and ambiguous place names. A single model can produce fluent but unsupported answers. SasineSense AI is designed around a different principle:

> **No extracted field should lose its evidence, method, confidence or validation state.**

The system keeps multiple candidates instead of silently overwriting conflicts, uses schema-constrained outputs, and gives experts a review surface with an append-only audit trail.

## What is implemented

| Capability | Implementation | Status |
| --- | --- | :---: |
| PDF/image ingestion and validation | FastAPI + PyMuPDF | ✅ |
| Page rendering and preprocessing | PyMuPDF + OpenCV/Pillow | ✅ |
| OCR adapter | Mock provider + Tesseract | ✅ |
| Deterministic extraction | Regex rules + document classifier | ✅ |
| Entity extraction | spaCy NER + EntityRuler | ✅ |
| Structured extraction | Mock provider + Mesh VLM adapter | ✅ |
| Candidate merge and provenance | Pydantic schemas | ✅ |
| Validation and confidence | Rule checks + review routing | ✅ |
| Place resolution | Ranked CSV gazetteer | ✅ |
| Human review | Streamlit reviewer | ✅ |
| Durable storage | SQLAlchemy, SQLite/Postgres-ready | ✅ |
| Evaluation | Field-level metrics and baseline report | ✅ |
| Bounded agents | Permissioned Triage/Verification/Consistency/Geo | ⏳ |

## Architecture

### End-to-end flow

```mermaid
flowchart TB
    subgraph intake["01 · INGEST & PREPARE"]
        A["Upload PDF or image"] --> B["Validate file<br/>persist metadata"]
        B --> C["Render pages"]
        C --> D{"Preprocessing<br/>enabled?"}
        D -->|"yes"| E["Enhance copies<br/>grayscale · deskew · denoise"]
        D -->|"no"| F["Use original<br/>page images"]
    end

    subgraph observe["02 · OBSERVE"]
        G["OCR provider"] --> H["OCR result<br/>text · tokens · boxes"]
        H --> I["Regex rules"]
        H --> J["spaCy NER"]
    end

    subgraph understand["03 · UNDERSTAND"]
        K["Schema-constrained<br/>VLM extraction"]
        L["Candidate merge<br/>preserve conflicts"]
        M["Evidence + validation"]
        N["Confidence +<br/>review routing"]
        I --> L
        J --> L
        K --> L
        L --> M --> N
    end

    subgraph resolve["04 · RESOLVE & REVIEW"]
        O["Ranked place<br/>resolver"]
        P[("SQLite / Postgres")]
        Q["Streamlit<br/>human review"]
        R["Append-only<br/>audit log"]
        O --> P
        O --> Q --> R
    end

    E --> G
    F --> G
    H --> K
    N --> O

    classDef input fill:#e8f1ff,stroke:#4b82c3,color:#102a43,stroke-width:2px;
    classDef process fill:#e8faf5,stroke:#20a47a,color:#103b31,stroke-width:2px;
    classDef quality fill:#fff4dc,stroke:#d99421,color:#4a2b00,stroke-width:2px;
    classDef review fill:#f3eaff,stroke:#8957c7,color:#281344,stroke-width:2px;
    class A,B,C,D,E,F input;
    class G,H,I,J,K,L process;
    class M,N,O quality;
    class P,Q,R review;
```

### Provider boundaries

```mermaid
flowchart LR
    CFG["Environment configuration<br/>.env · provider selection"]

    subgraph contracts["Stable application contracts"]
        PIPE["Pipeline orchestration"]
        OCRC["OCRProvider"]
        NERC["NERProvider"]
        VLMC["StructuredExtractionProvider"]
        GEOC["PlaceResolver"]
        OUT["PropertyRecordExtraction"]
        PIPE --> OCRC
        PIPE --> NERC
        PIPE --> VLMC
        PIPE --> GEOC
        PIPE --> OUT
    end

    subgraph implementations["Replaceable provider implementations"]
        OCRM["Mock OCR"]
        OCRT["Tesseract OCR"]
        NERS["spaCy NER<br/>EntityRuler"]
        VLMO["Mock structured extraction"]
        VLMM["Mesh vision-language model"]
        GEOCSV["CSV gazetteer"]
        GEOPG["PostGIS resolver<br/>future"]
    end

    OCRC -. "select one" .-> OCRM
    OCRC -. "select one" .-> OCRT
    NERC -. "uses" .-> NERS
    VLMC -. "select one" .-> VLMO
    VLMC -. "select one" .-> VLMM
    GEOC -. "select one" .-> GEOCSV
    GEOC -. "select one" .-> GEOPG
    CFG -. "configures" .-> OCRC
    CFG -. "configures" .-> VLMC
    CFG -. "configures" .-> GEOC

    classDef contract fill:#e8f1ff,stroke:#3977b8,color:#102a43,stroke-width:2px;
    classDef implementation fill:#e8faf5,stroke:#20a47a,color:#103b31,stroke-width:2px;
    classDef config fill:#fff4dc,stroke:#d99421,color:#4a2b00,stroke-width:2px;
    class PIPE,OCRC,NERC,VLMC,GEOC,OUT contract;
    class OCRM,OCRT,NERS,VLMO,VLMM,GEOCSV,GEOPG implementation;
    class CFG config;
```

The pipeline depends on interfaces rather than concrete vendors. Local/mock providers are the safe default; real providers can be enabled through environment variables without changing business logic.

### Human review loop

![Review workflow](docs/reviewer-flow.svg)

The reviewer can accept, edit, flag or mark a field unresolved. Each action records the document, field, previous value, new value, timestamp and note; history is never mutated in place.

## Structured output

Every field is represented as an evidence-bearing candidate. A simplified example:

```json
{
  "name": "property_location",
  "value": "Glasgow",
  "normalized_value": "Glasgow",
  "confidence": 0.93,
  "method": "regex+ner+vlm",
  "evidence": [{"page": 1, "text": "lands situated in Glasgow"}],
  "validation": {"status": "passed", "rules": ["non_empty", "place_resolved"]}
}
```

The top-level extraction includes document type/date, parties, property description, places, rights, burdens, servitudes, title references, map references, source pages, review state and metadata about every provider used.

### Real title-register example

This is a real sample image processed locally through the application with
Tesseract OCR, labelled title-sheet rules and evidence-preserving validation.
The image is included only as a demonstrator fixture; confirm that you have the
right to redistribute any real records used in your own corpus.

<div align="center">
  <img src="docs/assets/title-register-sample.jpg" alt="Registers of Scotland title-register sample" width="520">
  <br>
  <sub>Source document: title-register sample used for the local extraction demonstration.</sub>
</div>

The corresponding structured result promotes the fields that can be read from
the page and keeps their evidence, method and confidence visible:

| Extracted field | Result | Method | Confidence / review meaning |
| --- | --- | --- | --- |
| Document type | `title_sheet` | document classifier | Recognized as a title-sheet layout |
| Title reference | `MID113689` | regex | 75%; exact text found on page 1 |
| Proprietor | `DAT LYNCH INVESTMENTS PTY LTD` | labelled OCR/rules | Candidate; requires human confirmation |
| Property description | `FLAT 2 at 27 CASTLE TERRACE, EDINBURGH EH1 2EL` | description section parser | Evidence linked to the Description section |
| Registration dates | `06/05/2015`, `13/02/2008`, `12/12/2013`, `15/11/2013` | labelled/date OCR rules | Kept as separate dates; not collapsed into one arbitrary date |
| Consideration | `£190,000` | currency regex | Evidence linked to the proprietorship entry |
| Map reference | `NT2473SE` | focused crop OCR | Small-print candidate; review required |

In JSON, the same result is represented as reviewable fields rather than a
single untraceable answer:

```json
{
  "document_type": "title_sheet",
  "title_references": [{
    "value": "MID113689",
    "method": "regex",
    "confidence": 0.75,
    "evidence": [{"page": 1, "text": "MID113689"}]
  }],
  "property_description": {
    "value": "Subjects FLAT 2 at 27 CASTLE TERRACE, EDINBURGH EH1 2EL ...",
    "method": "labelled_regex",
    "evidence": [{"page": 1, "text": "Description: Subjects FLAT 2 ..."}]
  },
  "consideration": {"value": "£190,000", "method": "regex"},
  "map_references": [{
    "value": "NT2473SE",
    "method": "labelled_crop_ocr",
    "confidence": 0.78
  }],
  "review_required": true
}
```

The application deliberately keeps `review_required: true`: extracted values
assist research and triage, but they are not authoritative proof of ownership,
title or legal rights.

### Same document through every available method

The real sample was also passed through the local comparison runner so the
outputs can be inspected side by side. The full machine-readable record is in
[`docs/reports/title-register-comparison/results.json`](docs/reports/title-register-comparison/results.json), with a human-readable summary in [`docs/reports/title-register-comparison/README.md`](docs/reports/title-register-comparison/README.md).

| Method | What it returned on the sample | Status |
| --- | --- | :---: |
| Tesseract OCR only | Raw page text and OCR character count | ✅ |
| Tesseract + regex | Document type, dates, money, postcode and `MID113689` | ✅ |
| Tesseract + spaCy NER | PERSON/ORG/GPE/LOC candidates | ✅ |
| Labelled title-sheet rules | Property description, proprietor and map-field candidates | ✅ |
| Local hybrid | Full evidence-preserving structured result | ✅ |
| Mesh/VLM | Optional; requires configured credentials and `--mesh` | Not run |
| vLLM | Optional; requires an OpenAI-compatible endpoint and model | Not configured |

Run the same comparison yourself:

```bash
python -m app.eval.real_sample \
  --input docs/assets/title-register-sample.jpg \
  --out docs/reports/title-register-comparison
```

For a local vLLM server exposing `/v1/models`:

```bash
python -m app.eval.real_sample \
  --input docs/assets/title-register-sample.jpg \
  --vllm-base-url http://127.0.0.1:8000/v1 \
  --vllm-model your-vision-model
```

The comparison records unavailable systems explicitly. A missing Mesh/vLLM
endpoint is never presented as a successful extraction.

### Sample data to structured result

The repository includes a small gold annotation and Scotland gazetteer fixture. The following visual shows how that sample record is represented as a reviewable structured result with evidence, confidence and a resolved place.

![Sample annotation transformed into a structured result](docs/structured-result-example.svg)

## Quick start

### Install

```bash
git clone https://github.com/nitesh0007-edith/SasineSenseAI.git
cd SasineSenseAI
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env
```

### Run the API and reviewer

Terminal 1:

```bash
uvicorn app.api.main:app --reload
```

Terminal 2:

```bash
streamlit run app/ui/reviewer.py
```

Open `http://localhost:8501`, upload a PDF/image, and select **Run extraction**.

### Run quality checks

```bash
python -m pytest -q
python -m ruff check .
```

Current baseline: **82 tests passed, 1 skipped** and Ruff clean. The skipped test covers graceful behavior when the optional system Tesseract binary is unavailable.

### Batch processing an authorized corpus

Place authorized PDF/TIFF/image records in a local folder. The batch runner
does not download or discover archive records; it processes only files you have
permission to use and writes one auditable JSON object per line:

```bash
python -m app.batch.run \
  --input-dir ./data/source_records \
  --output ./data/derived/batch/results.jsonl \
  --ocr tesseract \
  --structured mesh
```

For a dry local trial without database writes:

```bash
python -m app.batch.run \
  --input-dir ./data/source_records \
  --output ./data/derived/batch/results.jsonl \
  --no-persist --ocr tesseract --structured mock
```

The runner uses content-stable document IDs, continues after individual file
errors, records failed files in the same JSONL output, and preserves provider,
confidence, evidence and review metadata for every successful extraction.

## Configuration

Providers are selected in `.env`:

```dotenv
OCR_PROVIDER=mock                         # mock | tesseract
NER_PROVIDER=spacy
STRUCTURED_EXTRACTION_PROVIDER=mock       # mock | mesh
PREPROCESS_ENABLED=false
DATABASE_URL=sqlite:///./data/derived/app.db
```

For real OCR, install Tesseract (`brew install tesseract` or `apt install tesseract-ocr`) and set `OCR_PROVIDER=tesseract`.

For real VLM extraction, set `STRUCTURED_EXTRACTION_PROVIDER=mesh` and provide a Mesh API key in a local, unsynced `.env`. Never commit credentials. The adapter sends OCR text plus page images, requests schema-constrained JSON, retries malformed JSON once, and uses `null` when uncertain.

## API

| Method | Endpoint | Purpose |
| :---: | --- | --- |
| `GET` | `/health` | Service health check |
| `POST` | `/documents` | Upload a PDF or image |
| `POST` | `/documents/{id}/extract` | Run the extraction pipeline |
| `POST` | `/documents/{id}/reviews` | Append a reviewer action |
| `GET` | `/documents/{id}/reviews` | Read review history |

Interactive OpenAPI documentation is available at `http://localhost:8000/docs` while the API is running.

## Evaluation

The evaluation harness compares the baseline ladder on labelled data:

1. OCR + regex
2. OCR + mock VLM
3. OCR + real VLM (optional)

```bash
python -m app.eval.run
MESH_API_KEY=... python -m app.eval.run --live
```

Reports are written to `data/derived/eval/baseline_comparison.csv` and `.md`. The checked-in example corpus is intentionally synthetic; a real annotated corpus is required for research-grade conclusions.

## Repository layout

```text
app/
├── batch/        authorized-folder batch runner and JSONL export
├── api/          FastAPI endpoints
├── core/         settings and configuration
├── db/           SQLAlchemy models and repository
├── eval/         metrics, harness and baseline runner
├── providers/    OCR, NER, VLM and place-resolver adapters
├── services/     ingestion, rendering, pipeline, merge, validation and review
└── ui/           Streamlit reviewer
data/             sample annotations and gazetteer fixtures
docs/             research plan, annotation guide and architecture visuals
tests/            unit and integration tests
```

## Roadmap

- [ ] Phase 12: bounded, permissioned agents for triage, verification, consistency and geo resolution.
- [ ] Replace the two-document synthetic corpus with real annotated public records.
- [ ] Expand the gazetteer and add a PostGIS-backed resolver with ranked candidates.
- [ ] Add Alembic migrations as persistence evolves.
- [ ] Feed spaCy PERSON/GPE candidates into the final merge path.
- [ ] Add CI, containerized API/UI deployment and observability.

## Research and safety notes

- See [`docs/RESEARCH_PLAN.md`](docs/RESEARCH_PLAN.md) for hypotheses and evaluation design.
- See [`docs/ANNOTATION_GUIDE.md`](docs/ANNOTATION_GUIDE.md) for gold-label conventions.
- Do not upload confidential or copyrighted records without the necessary rights.
- Do not treat generated output as legal advice or proof of ownership.
- Keep secrets in a local `.env`; `.gitignore` excludes credentials, uploads, derived data and databases.

## License

No production license has been declared yet. Treat this repository as a research prototype until a license and contribution policy are added.

<div align="center">Built for careful, explainable exploration of historical property records.</div>
