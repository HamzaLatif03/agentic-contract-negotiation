from pathlib import Path
import asyncio

import pytest
from fastapi.testclient import TestClient

from loan_negotiation.api.main import app
from loan_negotiation.services.contract_pdf import (
    ContractExtractionError,
    extract_offer_heuristically,
    extract_opening_offer_from_pdf,
    extract_text_from_pdf,
)

client = TestClient(app)

SAMPLE_PDF = Path(__file__).resolve().parents[1] / "samples" / "lender_opening_offer.pdf"

SAMPLE_TEXT = """
Lender Opening Loan Offer
Down payment: £70,000
Interest rate: 5.25% per annum
Loan term: 25 years
Interest type: fixed rate
"""


def test_extract_offer_heuristically_from_text():
    offer = extract_offer_heuristically(SAMPLE_TEXT)
    assert offer is not None
    assert offer.downpayment == 70000
    assert offer.interest_rate_pct == 5.25
    assert offer.loan_length_years == 25
    assert offer.interest_structure == 1
    assert offer.consensus_reached is False


def test_extract_offer_from_json_block_in_text():
    text = """
    Proposed terms:
    ```json
    {
      "downpayment": 65000,
      "interest_rate_pct": 4.9,
      "loan_length_years": 22,
      "interest_structure": 8,
      "consensus_reached": false
    }
    ```
    """
    offer = extract_offer_heuristically(text)
    assert offer is not None
    assert offer.downpayment == 65000
    assert offer.interest_structure == 8


def test_extract_opening_offer_from_sample_pdf():
    data = SAMPLE_PDF.read_bytes()
    text = extract_text_from_pdf(data)
    assert "70000" in text.replace(",", "") or "Down payment" in text
    offer, raw = asyncio.run(extract_opening_offer_from_pdf(data, use_llm=False))
    assert offer.downpayment == 70000
    assert offer.loan_length_years == 25
    assert offer.interest_rate_pct == 5.25
    assert offer.consensus_reached is False
    assert raw


def test_extract_text_rejects_empty_pdf_bytes():
    with pytest.raises(ContractExtractionError):
        extract_text_from_pdf(b"")


def test_parse_offer_pdf_endpoint():
    response = client.post(
        "/api/parse-offer-pdf",
        files={"file": ("lender_opening_offer.pdf", SAMPLE_PDF.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["opening_offer"]["downpayment"] == 70000
    assert data["opening_offer"]["interest_rate_pct"] == 5.25
    assert data["opening_offer"]["loan_length_years"] == 25
    assert data["opening_offer"]["interest_structure"] == 1


def test_parse_offer_pdf_rejects_non_pdf_name():
    response = client.post(
        "/api/parse-offer-pdf",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
