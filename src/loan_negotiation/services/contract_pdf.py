"""Extract plain text from lender offer PDFs (no LLM)."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


class ContractExtractionError(ValueError):
    """Raised when a PDF cannot be read as text."""


def extract_text_from_pdf(data: bytes) -> str:
    if not data:
        raise ContractExtractionError("Uploaded PDF is empty.")
    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - pypdf raises varied errors
        raise ContractExtractionError(f"Could not read PDF: {exc}") from exc

    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            pages.append("")
    text = "\n".join(pages).strip()
    if not text:
        raise ContractExtractionError(
            "No extractable text found in the PDF. Use a text-based (not scanned) offer."
        )
    return text
