from loan_negotiation.workflow.personas import PERSONAS, get_persona, list_personas
from loan_negotiation.services.feasibility import FeasibilityStatus, check_feasibility


def test_ten_personas_listed():
    rows = list_personas()
    assert len(rows) == 10
    assert rows[0]["id"] == "demo"
    ids = {row["id"] for row in rows}
    assert "impossible" in ids
    assert "features-duel" in ids


def test_demo_persona_is_feasible():
    persona = get_persona("demo")
    result = check_feasibility(persona.borrower, persona.lender)
    assert result.status == FeasibilityStatus.POSSIBLE


def test_impossible_persona_is_impossible():
    persona = get_persona("impossible")
    result = check_feasibility(persona.borrower, persona.lender)
    assert result.status == FeasibilityStatus.IMPOSSIBLE


def test_all_personas_have_feature_preferences():
    for persona in PERSONAS:
        for party in (persona.borrower, persona.lender):
            assert 1 <= party.portable_preference <= 10
            assert 1 <= party.free_valuation_preference <= 10
            assert 1 <= party.free_legal_preference <= 10
