from loan_negotiation.workflow.negotiation_messages import (
    extract_negotiator_text,
    format_negotiator_message,
)


def test_extract_negotiator_text_skips_bare_tool_ok():
    class Msg:
        source = "lender_negotiator"

        def to_text(self) -> str:
            return "OK: all four values are within your limits."

    assert extract_negotiator_text(Msg()) is None  # type: ignore[arg-type]


def test_extract_negotiator_text_formats_accept_message():
    class Msg:
        source = "borrower_negotiator"

        def to_text(self) -> str:
            return (
                'I accept.\n```json\n{"downpayment": 70000, "interest_rate_pct": 5.0, '
                '"loan_length_years": 25, "interest_structure": 1, "consensus_reached": true}\n```'
            )

    text = extract_negotiator_text(Msg())  # type: ignore[arg-type]

    assert text is not None
    assert "Accepting" in text
    assert "70,000" in text
    assert "fixed" in text


def test_format_negotiator_message_strips_tool_json():
    raw = (
        '{"summary": "Counter offer:", "parameters": {"downpayment":"65000"}} '
        '```json\n{"downpayment":65000,"interest_rate_pct":4.75,'
        '"loan_length_years":20,"interest_structure":9,"consensus_reached":false}\n```'
    )

    formatted = format_negotiator_message(raw)

    assert "summary" not in formatted
    assert "Offering" in formatted
    assert "65,000" in formatted


def test_extract_negotiator_text_skips_goodbye_noise():
    class Msg:
        source = "lender_negotiator"

        def to_text(self) -> str:
            return "Goodbye! The negotiation is closed."

    assert extract_negotiator_text(Msg()) is None  # type: ignore[arg-type]
