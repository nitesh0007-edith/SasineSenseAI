# Research Plan

## Working title
AI-Assisted Scottish Property Record Intelligence

## Primary hypothesis
A hybrid extraction pipeline using OCR/HTR + deterministic rules + NER + VLM structured extraction + validation will achieve higher field-level accuracy and lower unsupported-extraction rate than OCR-only or VLM-only approaches.

## Secondary hypotheses
1. Evidence-constrained extraction reduces hallucinated fields.
2. Rule-based validation improves precision for structured fields such as dates and references.
3. Grouped evaluation by era/template gives a more realistic estimate of production generalization than random splitting.
4. Human-review routing can reduce manual workload while preserving high-accuracy thresholds.

## Baselines
- OCR only
- OCR + regex
- OCR + regex + spaCy
- VLM only
- OCR + VLM
- Hybrid

## Suggested MVP fields
- document type
- document date
- parties
- place names
- property description
- title/reference numbers

## Important exclusions
Do not claim:
- legal title determination;
- automated adjudication;
- authoritative RoS compatibility;
- production-grade accuracy without evidence.
