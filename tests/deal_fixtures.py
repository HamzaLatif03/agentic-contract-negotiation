"""Helpers shared by negotiation/parser tests."""

from loan_negotiation.models.loan_terms import DealTerms


def sample_deal(**overrides) -> DealTerms:
    defaults = {
        "downpayment": 65_000,
        "interest_rate_pct": 4.8,
        "loan_length_years": 25,
        "rate_type": "fixed",
        "initial_period_years": 5,
        "arrangement_fee": 999,
        "cashback": 500,
        "overpayment_allowance_pct": 10,
        "erc_pct": 2,
        "repayment_type": "capital_repayment",
        "portable": True,
        "free_valuation": True,
        "free_legal": False,
        "consensus_reached": False,
    }
    defaults.update(overrides)
    return DealTerms(**defaults)


DEAL_JSON = """\
{
  "downpayment": 65000,
  "interest_rate_pct": 4.8,
  "loan_length_years": 25,
  "rate_type": "fixed",
  "initial_period_years": 5,
  "arrangement_fee": 999,
  "cashback": 500,
  "overpayment_allowance_pct": 10,
  "erc_pct": 2,
  "repayment_type": "capital_repayment",
  "portable": true,
  "free_valuation": true,
  "free_legal": false,
  "consensus_reached": false
}
"""
