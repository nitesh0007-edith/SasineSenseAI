# Annotation Guide

Create gold-standard annotations for evaluation.

## Required minimum fields
- document_id
- document_type
- page number
- document date, if visible
- named parties
- place names
- property description, if extractable
- title/reference identifiers, if present

## Evidence
Every field must include source evidence.

## Ambiguity
If the document is unclear:
- keep `value = null` if unknown;
- use `ambiguous = true`;
- provide annotation note.

Do not infer facts not visibly supported by the document.

## Suggested JSONL item

```json
{
  "document_id": "sample_001",
  "document_type": "disposition",
  "fields": {
    "document_date": {
      "value": "1876-05-12",
      "page": 1,
      "evidence_text": "dated 12 May 1876"
    }
  },
  "parties": [
    {
      "name": "John Campbell",
      "role": "granter",
      "page": 1,
      "evidence_text": "by John Campbell"
    }
  ],
  "places": [
    {
      "name": "Glasgow",
      "page": 1,
      "evidence_text": "lands situated in Glasgow"
    }
  ]
}
```
