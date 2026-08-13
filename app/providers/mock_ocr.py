from pathlib import Path

from app.models.schemas import OCRPageResult


class MockOCRProvider:
    name = "mock"

    def extract_page(self, image_path: Path, page_number: int) -> OCRPageResult:
        text = (
            "Disposition dated 12 May 1876 by John Campbell in favour of Mary Fraser "
            "concerning lands situated in Glasgow."
        )
        return OCRPageResult(
            page=page_number,
            text=text,
            tokens=[],
            provider=self.name,
            provider_version="0.1",
        )
