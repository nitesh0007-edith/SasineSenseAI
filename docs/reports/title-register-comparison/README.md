# Real title-register comparison

Source: `docs/assets/title-register-sample.jpg`

This is a method comparison over one real sample, not a statistically representative benchmark.

| System | Status | What it demonstrates |
| --- | --- | --- |
| `ocr_only` | `completed` | Raw Tesseract text and page count |
| `ocr_regex` | `completed` | Dates, money, postcodes and title references |
| `ocr_spacy_ner` | `completed` | PERSON/ORG/GPE/LOC entity candidates |
| `labelled_rules` | `completed` | Title-sheet sections and labelled fields |
| `hybrid_local` | `completed` | Full evidence-preserving local pipeline |
| `mesh_vlm` | `not_run` | Mesh/VLM endpoint result |
| `vllm` | `not_configured` | vLLM OpenAI-compatible endpoint result |

## Local hybrid output

The complete JSON output is in [`results.json`](results.json). Key fields extracted from the sample:

- title reference: `MID113689`
- proprietor candidate: `DAT LYNCH INVESTMENTS PTY LTD`
- property description: `FLAT 2 at 27 CASTLE TERRACE, EDINBURGH EH1 2EL`
- consideration: `£190,000`
- map reference: `NT2473SE`
- registration/title-sheet dates retained separately for review

Systems marked `not_configured` or `unavailable` were not treated as successful extractions.
