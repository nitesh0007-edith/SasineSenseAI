# Handoff notes

_Last updated: 2026-08-13_

Working session context for the next person (or next Claude session) picking up
**SasineSense AI** (the `ros_property_ai_starter` prototype).

---

## 1. Where the project stands

The **first milestone is complete and then some**. End-to-end flow works:
upload → render → (optional preprocess) → OCR → regex + spaCy NER → structured
extraction (mock **or real VLM**) → candidate merge → validation + confidence →
place resolution → review routing → Streamlit review, with durable persistence.

Phase status (see README §13 for the full table):

- Phases 0–11: ✅ done, with tests.
- Real OCR (Tesseract) and real VLM (Mesh API): ✅ wired and **live-verified**.
- Persistence (SQLAlchemy, SQLite default / Postgres-ready): ✅ done.
- Phase 12 (bounded agents): ⏳ **not started — intentionally deferred** until the
  milestone was solid. This is the natural next build.

**Tests:** `python -m pytest` → 82 passed, 1 skipped (the skip is the
"tesseract-absent" graceful-failure test; it self-skips because tesseract IS
installed here). `python -m ruff check .` → clean.

> First full test run in a fresh shell takes ~100s because spaCy `en_core_web_sm`
> loads cold; subsequent runs are ~5s (warm OS cache). Nothing is hanging.

---

## 2. How to run things

```bash
# API + UI
uvicorn app.api.main:app --reload
streamlit run app/ui/reviewer.py

# Tests / lint
python -m pytest -q
python -m ruff check .

# Phase 11 baseline comparison (synthetic corpus)
python -m app.eval.run                               # OCR+regex, OCR+mock-VLM (no network)
MESH_API_KEY=rsk_... python -m app.eval.run --live   # + real OCR + real Mesh VLM
# -> writes data/derived/eval/baseline_comparison.{csv,md}
```

Latest **live** comparison (real Tesseract + Claude Sonnet 5 via Mesh), field F1:
`ocr+regex 0.429` · `ocr+mock_vlm 0.600` · **`ocr+mesh_vlm 0.818`**. Hybrid wins
on recall (0.90) while holding precision (0.75) — supports the core hypothesis.

---

## 3. Environment / dependencies (already installed on this machine)

- `tesseract` 5.5.3 via Homebrew; `pytesseract` via pip → real OCR active.
- `spacy` + `en_core_web_sm` → real NER active.
- `ruff` 0.16.3 installed.
- Python 3.13 (anaconda). `cv2`, `numpy`, `sqlalchemy` present.
- **Missing / not used:** `dateparser` (regex date parsing is hand-rolled, fine).

A fresh clone on another machine needs: `pip install -r requirements.txt`,
`python -m spacy download en_core_web_sm`, and a system `tesseract` binary.

---

## 4. Providers & config (important design points)

- Providers are selected by config via `app/providers/factory.py` — nothing is
  hard-wired into the pipeline. Env/`.env` keys:
  - `OCR_PROVIDER` = `mock` | `tesseract`
  - `STRUCTURED_EXTRACTION_PROVIDER` = `mock` | `mesh`
  - `NER_PROVIDER` = `spacy`
- **Mesh API** (`providers/mesh_structured.py`) is OpenAI-compatible
  (`https://api.meshapi.ai/v1`, Bearer `rsk_...` key). Sends image + OCR text,
  returns schema-constrained JSON, retries once on malformed JSON, uses `null`
  when uncertain. Default model `anthropic/claude-sonnet-5`.
  - GOTCHA: do **not** send `temperature` — newer models 400 on it as deprecated.
    The provider already omits it.
  - The docs' example model `anthropic/claude-3-5-sonnet` is stale → 404. Use the
    live `/v1/models` catalog (1000+ models). Opus 4.8 etc. are available but
    pricier per page; Sonnet 5 is the chosen default.
- Persistence: `app/db/` — defaults to `sqlite:///./data/derived/app.db`. Set
  `DATABASE_URL=postgresql+psycopg://...` for Postgres/PostGIS. Review actions are
  **append-only** in both the JSONL log and the DB (history is never mutated).

---

## 5. SECURITY — read this

- The user pasted a live Mesh key (`rsk_01KZY...`) into chat. It was used **only
  in-process** for live runs and is **not written to any file** (grep-verified).
- **ACTION FOR USER: rotate that key** — it was exposed in plaintext chat.
- A `.gitignore` was added (the project had none; the git root is the user's home
  dir). It ignores `.env`, `data/`, `*.db`, caches. `.env.example` holds only a
  placeholder key.
- This project folder is **Google Drive-synced**. Prefer keeping real secrets in a
  non-synced local `.env`, not in this directory.

---

## 6. Recommended next tasks (in priority order)

1. **Phase 12 — bounded agents** (Triage / Verification / Consistency / Geo). Must
   be orchestrated tools with deterministic permissions + logging, NOT free-form
   autonomous agents. See CODEX_TASKS.md §12. Everything they need (classify,
   validate, place-resolve) already exists as services/providers.
2. **Real annotated corpus** — the Phase 11 corpus is synthetic (2 docs in
   `app/eval/run.py::CORPUS`). Collect real public property records + gold
   annotations (`docs/ANNOTATION_GUIDE.md`) for a research-grade comparison.
3. **Gazetteer**: still the 3-row sample CSV. User chose "sample fine for now."
   When ready, add a GeoNames GB importer and/or the PostGIS resolver (Task 9.3);
   `PlaceResolver` interface already exists in `providers/base.py`.
4. **Alembic migrations** if the DB schema starts to evolve (currently
   `Base.metadata.create_all` via `init_db`).
5. NER currently feeds candidate counts into metadata but isn't merged into the
   final parties/places yet — wiring spaCy PERSON/GPE into the merge step would
   strengthen the non-VLM baselines.

---

## 7. Key files added this session

- `app/providers/mesh_structured.py` — real VLM provider (Task 7.3)
- `app/providers/tesseract_ocr.py`, `app/providers/factory.py` — real OCR + selection
- `app/db/{base,models,repository}.py` — persistence
- `app/eval/{metrics,harness,run}.py` — Phase 11 harness + runner
- `app/services/{preprocessing,merge,validation,review}.py` — Phases 2/6.2/8/10
- `app/providers/spacy_ner.py`, expanded `app/services/rules.py` — Phases 5/4
- Tests: `tests/test_{preprocessing,ner,merge,validation,gazetteer,ocr_providers,review,eval,eval_runner,persistence,mesh_provider}.py`
- `.gitignore`, `docs/HANDOFF.md`
