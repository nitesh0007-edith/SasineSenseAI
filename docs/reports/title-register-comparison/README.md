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
| `mesh_vlm` | `completed` | Mesh/VLM endpoint result |
| `vllm` | `not_configured` | vLLM OpenAI-compatible endpoint result |

## Local hybrid output

The complete JSON output is in [`results.json`](results.json). Key fields extracted from the sample:

- title reference: `MID113689`
- proprietor candidate: `DAT LYNCH INVESTMENTS PTY LTD`
- property description: `FLAT 2 at 27 CASTLE TERRACE, EDINBURGH EH1 2EL`
- consideration: `£190,000`
- map reference: `NT2473SE`
- registration/title-sheet dates retained separately for review

## Mesh/VLM output

The live Mesh run used `anthropic/claude-sonnet-5` through the configured
OpenAI-compatible gateway. It returned `title_sheet`, proprietor candidate
`D & T LYNCH INVESTMENTS PTY LTD`, a semantic property description,
`£190,000`, title references `MID113689` and `Sasine Search Sheet: 181920`,
and place candidates for Edinburgh and the registered office in Melbourne.
The pipeline retained `review_required: true` with overall confidence `0.634`.

The local rules recovered the precise map reference `NT2473SE`; Mesh did not
return that field. Conversely, Mesh provided richer semantic context but also
returned a registered-office place that requires reviewer interpretation.

Systems marked `not_configured` or `unavailable` were not treated as successful extractions.
