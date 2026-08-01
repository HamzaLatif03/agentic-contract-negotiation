from io import BytesIO

import pytest
from pypdf import PdfWriter

from deal_fixtures import sample_deal
from loan_negotiation.services.contract_pdf import (
    ContractExtractionError,
    extract_text_from_pdf,
)
from loan_negotiation.services.opening_offer import format_opening_offer_announcement


def _pdf_bytes_with_text(text: str) -> bytes:
    """Build a tiny text PDF in-memory (no on-disk sample required)."""
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode("latin-1")
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        (
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
        ),
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("latin-1")
        + stream
        + b"\nendstream\nendobj\n",
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    return bytes(out)


def test_extract_text_from_pdf():
    pdf = _pdf_bytes_with_text("Down payment: 70000")
    text = extract_text_from_pdf(pdf)
    assert "70000" in text.replace(",", "") or "Down payment" in text


def test_extract_text_rejects_empty_pdf_bytes():
    with pytest.raises(ContractExtractionError):
        extract_text_from_pdf(b"")


def test_extract_text_rejects_blank_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    with pytest.raises(ContractExtractionError, match="No extractable text"):
        extract_text_from_pdf(buf.getvalue())


def test_format_opening_offer_announcement():
    offer = sample_deal(
        downpayment=70_000,
        interest_rate_pct=5.25,
        loan_length_years=25,
        rate_type="fixed",
        consensus_reached=False,
    )
    text = format_opening_offer_announcement(offer)
    assert "£70,000" in text
    assert "5.25%" in text
    assert "fixed" in text
    assert "downpayment" in text
