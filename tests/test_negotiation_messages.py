from loan_negotiation.workflow.negotiation_messages import (
    NegotiationTracker,
    describe_offer_changes,
    extract_negotiator_text,
    format_negotiator_message,
)
from loan_negotiation.workflow.prompts import NEGOTIATOR_SHARED_RULES
from deal_fixtures import DEAL_JSON, sample_deal


def test_extract_negotiator_text_skips_bare_tool_ok():
    class Msg:
        source = "lender_negotiator"

        def to_text(self) -> str:
            return "OK: all values are within your limits."

    assert extract_negotiator_text(Msg()) is None  # type: ignore[arg-type]


def test_extract_negotiator_text_formats_accept_message():
    class Msg:
        source = "borrower_negotiator"

        def to_text(self) -> str:
            accept = DEAL_JSON.replace('"consensus_reached": false', '"consensus_reached": true')
            return f"I accept.\n```json\n{accept}\n```"

    text = extract_negotiator_text(Msg())  # type: ignore[arg-type]
    assert text is not None
    assert "Accepting" in text
    assert "Reasoning:" not in text
    assert "65,000" in text
    assert "fixed" in text


def test_format_negotiator_message_strips_tool_json():
    raw = (
        '{"summary": "Counter offer:", "parameters": {"downpayment":"65000"}} '
        f"```json\n{DEAL_JSON}\n```"
    )
    formatted = format_negotiator_message(raw)
    assert "summary" not in formatted
    assert "Offering" in formatted
    assert "Reasoning:" not in formatted
    assert "65,000" in formatted


def test_format_strips_reasoning_label_from_model_prose():
    raw = f"Reasoning: Fee is too high for us.\n```json\n{DEAL_JSON}\n```"
    formatted = format_negotiator_message(raw)
    assert "Reasoning:" not in formatted
    assert "Fee is too high" in formatted
    assert "Offering" in formatted


def test_extract_negotiator_text_skips_goodbye_noise():
    class Msg:
        source = "lender_negotiator"

        def to_text(self) -> str:
            return "Goodbye! The negotiation is closed."

    assert extract_negotiator_text(Msg()) is None  # type: ignore[arg-type]


def test_format_nemotron_xml_tool_call_as_offer():
    raw = """
<tool_call>
<function=check_offer>
<parameter=downpayment>90000</parameter>
<parameter=interest_rate_pct>5.0</parameter>
<parameter=loan_length_years>15</parameter>
<parameter=rate_type>fixed</parameter>
<parameter=initial_period_years>5</parameter>
<parameter=arrangement_fee>999</parameter>
<parameter=cashback>500</parameter>
<parameter=overpayment_allowance_pct>10</parameter>
<parameter=erc_pct>2</parameter>
<parameter=repayment_type>capital_repayment</parameter>
<parameter=portable>true</parameter>
<parameter=free_valuation>true</parameter>
<parameter=free_legal>false</parameter>
</function>
</tool_call>
"""
    formatted = format_negotiator_message(raw)
    assert "Offering" in formatted
    assert "Reasoning:" not in formatted
    assert "90,000" in formatted
    assert "5.0%" in formatted
    assert "15yr term" in formatted
    assert "<tool_call>" not in formatted


def test_tracker_adds_delta_justification_when_model_omits_prose():
    tracker = NegotiationTracker()
    opening = f"```json\n{DEAL_JSON}\n```"
    first = tracker.format_for_display("lender_negotiator", opening)
    assert first is not None
    assert "Reasoning:" not in first
    assert "Opening" in first or "Offering" in first

    counter = sample_deal(downpayment=70_000, cashback=1_500, consensus_reached=False)
    raw_counter = f"```json\n{counter.model_dump_json(indent=2)}\n```"
    second = tracker.format_for_display("borrower_negotiator", raw_counter)
    assert second is not None
    assert "Reasoning:" not in second
    assert "deposit" in second.lower() or "cashback" in second.lower() or "Adjusting" in second


def test_describe_offer_changes_lists_field_moves():
    previous = sample_deal(downpayment=70_000, cashback=500)
    current = sample_deal(downpayment=65_000, cashback=1_500)
    text = describe_offer_changes(current, previous, counterpart=previous)
    assert "deposit" in text
    assert "cashback" in text


def test_prompt_forbids_reasoning_label_and_knowing_other_limits():
    assert "Do NOT use labels like \"Reasoning:\"" in NEGOTIATOR_SHARED_RULES
    assert "You do NOT know theirs" in NEGOTIATOR_SHARED_RULES or (
        "You do NOT know the other party's" in NEGOTIATOR_SHARED_RULES
    )
    assert "non-negotiable" in NEGOTIATOR_SHARED_RULES.lower()
    assert "Open FIRST with YOUR preferred opening package" in __import__(
        "loan_negotiation.workflow.prompts", fromlist=["LENDER_NEGOTIATOR_PROMPT"]
    ).LENDER_NEGOTIATOR_PROMPT
