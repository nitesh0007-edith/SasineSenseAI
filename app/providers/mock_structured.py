from pathlib import Path

from app.models.schemas import (
    EvidenceSpan,
    ExtractedField,
    OCRPageResult,
    Party,
    PlaceCandidate,
    PropertyRecordExtraction,
)


class MockStructuredExtractionProvider:
    name = "mock"

    def extract(
        self,
        *,
        document_id: str,
        ocr_pages: list[OCRPageResult],
        page_images: list[Path],
        context: dict | None = None,
    ) -> PropertyRecordExtraction:
        page = ocr_pages[0].page if ocr_pages else 1
        text = ocr_pages[0].text if ocr_pages else ""

        evidence = EvidenceSpan(
            page=page,
            text=text,
            bbox=None,
            source="mock_structured_extraction",
        )

        return PropertyRecordExtraction(
            document_id=document_id,
            document_type="disposition",
            document_date=ExtractedField(
                name="document_date",
                value="12 May 1876",
                normalized_value="1876-05-12",
                confidence=0.92,
                method="mock_vlm",
                evidence=[evidence],
            ),
            parties=[
                Party(name="John Campbell", role="granter", confidence=0.90, evidence=[evidence]),
                Party(name="Mary Fraser", role="grantee", confidence=0.90, evidence=[evidence]),
            ],
            places=[
                PlaceCandidate(
                    name="Glasgow",
                    normalized_name="Glasgow",
                    confidence=0.95,
                    evidence=[evidence],
                )
            ],
            source_pages=[page],
            overall_confidence=0.91,
            review_required=True,
            metadata={"provider": self.name},
        )
