"""Named UK mortgage negotiation personas (borrower + lender pairs)."""

from __future__ import annotations

from dataclasses import dataclass

from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    description: str
    tag: str
    borrower: BorrowerTerms
    lender: LenderTerms

    def to_api_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tag": self.tag,
            "borrower": self.borrower.model_dump(),
            "lender": self.lender.model_dump(),
        }


def _party(**kwargs) -> dict:
    return kwargs


PERSONAS: tuple[Persona, ...] = (
    Persona(
        id="demo",
        name="Demo",
        tag="balanced",
        description=(
            "Mid-market overlap on rate and deposit. Borrower leans fixed + freebies; "
            "lender leans tracker and resists extras. Healthy multi-round room."
        ),
        borrower=BorrowerTerms(
            **_party(
                min_downpayment=60_000,
                max_downpayment=80_000,
                min_interest_rate_pct=4.0,
                max_interest_rate_pct=5.5,
                min_loan_length_years=20,
                max_loan_length_years=25,
                min_arrangement_fee=0,
                max_arrangement_fee=999,
                min_cashback=500,
                max_cashback=5_000,
                min_overpayment_allowance_pct=10,
                max_overpayment_allowance_pct=20,
                min_erc_pct=0,
                max_erc_pct=3,
                preferred_rate_type="fixed",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=8,
                free_valuation_preference=7,
                free_legal_preference=7,
            )
        ),
        lender=LenderTerms(
            **_party(
                min_downpayment=50_000,
                max_downpayment=100_000,
                min_interest_rate_pct=4.5,
                max_interest_rate_pct=6.0,
                min_loan_length_years=10,
                max_loan_length_years=30,
                min_arrangement_fee=0,
                max_arrangement_fee=1_499,
                min_cashback=0,
                max_cashback=2_000,
                min_overpayment_allowance_pct=5,
                max_overpayment_allowance_pct=10,
                min_erc_pct=1,
                max_erc_pct=5,
                preferred_rate_type="tracker",
                preferred_initial_period_years=2,
                preferred_repayment_type="capital_repayment",
                portable_preference=3,
                free_valuation_preference=3,
                free_legal_preference=2,
            )
        ),
    ),
    Persona(
        id="impossible",
        name="Impossible",
        tag="no-overlap",
        description=(
            "No overlapping rate band (and deposit also gapped). Feasibility should fail "
            "before negotiation starts."
        ),
        borrower=BorrowerTerms(
            **_party(
                min_downpayment=20_000,
                max_downpayment=40_000,
                min_interest_rate_pct=3.0,
                max_interest_rate_pct=4.0,
                min_loan_length_years=25,
                max_loan_length_years=35,
                min_arrangement_fee=0,
                max_arrangement_fee=500,
                min_cashback=2_000,
                max_cashback=5_000,
                min_overpayment_allowance_pct=15,
                max_overpayment_allowance_pct=25,
                min_erc_pct=0,
                max_erc_pct=1,
                preferred_rate_type="fixed",
                preferred_initial_period_years=10,
                preferred_repayment_type="capital_repayment",
                portable_preference=9,
                free_valuation_preference=9,
                free_legal_preference=9,
            )
        ),
        lender=LenderTerms(
            **_party(
                min_downpayment=70_000,
                max_downpayment=120_000,
                min_interest_rate_pct=5.5,
                max_interest_rate_pct=7.0,
                min_loan_length_years=10,
                max_loan_length_years=20,
                min_arrangement_fee=999,
                max_arrangement_fee=2_000,
                min_cashback=0,
                max_cashback=250,
                min_overpayment_allowance_pct=5,
                max_overpayment_allowance_pct=10,
                min_erc_pct=3,
                max_erc_pct=6,
                preferred_rate_type="tracker",
                preferred_initial_period_years=2,
                preferred_repayment_type="capital_repayment",
                portable_preference=1,
                free_valuation_preference=1,
                free_legal_preference=1,
            )
        ),
    ),
    Persona(
        id="knife-edge-borrower",
        name="Knife-edge (borrower best)",
        tag="single-point",
        description=(
            "Ranges only meet at the borrower's best / lender's worst on rate and deposit. "
            "Any deal is at that knife-edge point."
        ),
        borrower=BorrowerTerms(
            **_party(
                min_downpayment=60_000,
                max_downpayment=65_000,
                min_interest_rate_pct=4.0,
                max_interest_rate_pct=4.5,
                min_loan_length_years=25,
                max_loan_length_years=30,
                min_arrangement_fee=0,
                max_arrangement_fee=0,
                min_cashback=1_500,
                max_cashback=3_000,
                min_overpayment_allowance_pct=10,
                max_overpayment_allowance_pct=15,
                min_erc_pct=0,
                max_erc_pct=1,
                preferred_rate_type="fixed",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=9,
                free_valuation_preference=8,
                free_legal_preference=8,
            )
        ),
        lender=LenderTerms(
            **_party(
                min_downpayment=65_000,
                max_downpayment=110_000,
                min_interest_rate_pct=4.5,
                max_interest_rate_pct=6.5,
                min_loan_length_years=15,
                max_loan_length_years=30,
                min_arrangement_fee=0,
                max_arrangement_fee=1_999,
                min_cashback=0,
                max_cashback=1_500,
                min_overpayment_allowance_pct=5,
                max_overpayment_allowance_pct=10,
                min_erc_pct=1,
                max_erc_pct=5,
                preferred_rate_type="tracker",
                preferred_initial_period_years=2,
                preferred_repayment_type="capital_repayment",
                portable_preference=2,
                free_valuation_preference=2,
                free_legal_preference=2,
            )
        ),
    ),
    Persona(
        id="knife-edge-lender",
        name="Knife-edge (lender best)",
        tag="single-point",
        description=(
            "Ranges only meet at the lender's best / borrower's worst on rate and deposit. "
            "Mirror of the borrower knife-edge."
        ),
        borrower=BorrowerTerms(
            **_party(
                min_downpayment=50_000,
                max_downpayment=80_000,
                min_interest_rate_pct=4.0,
                max_interest_rate_pct=5.5,
                min_loan_length_years=20,
                max_loan_length_years=30,
                min_arrangement_fee=0,
                max_arrangement_fee=1_000,
                min_cashback=500,
                max_cashback=2_000,
                min_overpayment_allowance_pct=10,
                max_overpayment_allowance_pct=20,
                min_erc_pct=0,
                max_erc_pct=3,
                preferred_rate_type="fixed",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=7,
                free_valuation_preference=7,
                free_legal_preference=6,
            )
        ),
        lender=LenderTerms(
            **_party(
                min_downpayment=80_000,
                max_downpayment=100_000,
                min_interest_rate_pct=5.5,
                max_interest_rate_pct=6.5,
                min_loan_length_years=15,
                max_loan_length_years=25,
                min_arrangement_fee=999,
                max_arrangement_fee=1_499,
                min_cashback=0,
                max_cashback=500,
                min_overpayment_allowance_pct=5,
                max_overpayment_allowance_pct=10,
                min_erc_pct=3,
                max_erc_pct=5,
                preferred_rate_type="tracker",
                preferred_initial_period_years=2,
                preferred_repayment_type="capital_repayment",
                portable_preference=2,
                free_valuation_preference=2,
                free_legal_preference=1,
            )
        ),
    ),
    Persona(
        id="wide-open",
        name="Wide open",
        tag="flexible",
        description=(
            "Very large overlapping ranges and near-neutral feature prefs (≈5). "
            "Agents have lots of room to trade."
        ),
        borrower=BorrowerTerms(
            **_party(
                min_downpayment=20_000,
                max_downpayment=150_000,
                min_interest_rate_pct=3.5,
                max_interest_rate_pct=7.0,
                min_loan_length_years=10,
                max_loan_length_years=40,
                min_arrangement_fee=0,
                max_arrangement_fee=2_500,
                min_cashback=0,
                max_cashback=10_000,
                min_overpayment_allowance_pct=5,
                max_overpayment_allowance_pct=25,
                min_erc_pct=0,
                max_erc_pct=5,
                preferred_rate_type="fixed",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=5,
                free_valuation_preference=5,
                free_legal_preference=5,
            )
        ),
        lender=LenderTerms(
            **_party(
                min_downpayment=10_000,
                max_downpayment=200_000,
                min_interest_rate_pct=3.0,
                max_interest_rate_pct=8.0,
                min_loan_length_years=5,
                max_loan_length_years=40,
                min_arrangement_fee=0,
                max_arrangement_fee=3_000,
                min_cashback=0,
                max_cashback=8_000,
                min_overpayment_allowance_pct=0,
                max_overpayment_allowance_pct=20,
                min_erc_pct=0,
                max_erc_pct=6,
                preferred_rate_type="tracker",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=5,
                free_valuation_preference=5,
                free_legal_preference=5,
            )
        ),
    ),
    Persona(
        id="tight-squeeze",
        name="Tight squeeze",
        tag="narrow",
        description=(
            "Tiny overlapping windows on rate, deposit, and incentives. Little flexibility; "
            "small moves decide the deal."
        ),
        borrower=BorrowerTerms(
            **_party(
                min_downpayment=74_000,
                max_downpayment=76_000,
                min_interest_rate_pct=4.9,
                max_interest_rate_pct=5.1,
                min_loan_length_years=24,
                max_loan_length_years=26,
                min_arrangement_fee=900,
                max_arrangement_fee=1_100,
                min_cashback=400,
                max_cashback=600,
                min_overpayment_allowance_pct=9,
                max_overpayment_allowance_pct=11,
                min_erc_pct=1.5,
                max_erc_pct=2.5,
                preferred_rate_type="fixed",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=6,
                free_valuation_preference=6,
                free_legal_preference=5,
            )
        ),
        lender=LenderTerms(
            **_party(
                min_downpayment=75_000,
                max_downpayment=78_000,
                min_interest_rate_pct=5.0,
                max_interest_rate_pct=5.2,
                min_loan_length_years=25,
                max_loan_length_years=27,
                min_arrangement_fee=999,
                max_arrangement_fee=1_200,
                min_cashback=300,
                max_cashback=500,
                min_overpayment_allowance_pct=8,
                max_overpayment_allowance_pct=10,
                min_erc_pct=2,
                max_erc_pct=3,
                preferred_rate_type="fixed",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=4,
                free_valuation_preference=4,
                free_legal_preference=4,
            )
        ),
    ),
    Persona(
        id="strict-borrower",
        name="Strict borrower",
        tag="asymmetric",
        description=(
            "Borrower has narrow ranges and must-have freebies (9–10). Lender is flexible "
            "with soft feature prefs — classic concede-to-close for the bank."
        ),
        borrower=BorrowerTerms(
            **_party(
                min_downpayment=55_000,
                max_downpayment=65_000,
                min_interest_rate_pct=4.2,
                max_interest_rate_pct=4.8,
                min_loan_length_years=25,
                max_loan_length_years=25,
                min_arrangement_fee=0,
                max_arrangement_fee=499,
                min_cashback=2_000,
                max_cashback=4_000,
                min_overpayment_allowance_pct=15,
                max_overpayment_allowance_pct=20,
                min_erc_pct=0,
                max_erc_pct=1,
                preferred_rate_type="fixed",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=10,
                free_valuation_preference=10,
                free_legal_preference=9,
            )
        ),
        lender=LenderTerms(
            **_party(
                min_downpayment=40_000,
                max_downpayment=120_000,
                min_interest_rate_pct=4.0,
                max_interest_rate_pct=6.5,
                min_loan_length_years=15,
                max_loan_length_years=35,
                min_arrangement_fee=0,
                max_arrangement_fee=2_000,
                min_cashback=0,
                max_cashback=5_000,
                min_overpayment_allowance_pct=5,
                max_overpayment_allowance_pct=20,
                min_erc_pct=0,
                max_erc_pct=5,
                preferred_rate_type="discount",
                preferred_initial_period_years=2,
                preferred_repayment_type="capital_repayment",
                portable_preference=4,
                free_valuation_preference=4,
                free_legal_preference=3,
            )
        ),
    ),
    Persona(
        id="strict-lender",
        name="Strict lender",
        tag="asymmetric",
        description=(
            "Lender has tight pricing and refuses freebies (prefs 1–2). Borrower is flexible "
            "on numbers but still wants product features — force real trade-offs."
        ),
        borrower=BorrowerTerms(
            **_party(
                min_downpayment=40_000,
                max_downpayment=120_000,
                min_interest_rate_pct=3.5,
                max_interest_rate_pct=6.5,
                min_loan_length_years=15,
                max_loan_length_years=35,
                min_arrangement_fee=0,
                max_arrangement_fee=2_000,
                min_cashback=0,
                max_cashback=6_000,
                min_overpayment_allowance_pct=5,
                max_overpayment_allowance_pct=20,
                min_erc_pct=0,
                max_erc_pct=5,
                preferred_rate_type="fixed",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=8,
                free_valuation_preference=7,
                free_legal_preference=7,
            )
        ),
        lender=LenderTerms(
            **_party(
                min_downpayment=70_000,
                max_downpayment=85_000,
                min_interest_rate_pct=5.2,
                max_interest_rate_pct=5.8,
                min_loan_length_years=20,
                max_loan_length_years=25,
                min_arrangement_fee=999,
                max_arrangement_fee=1_499,
                min_cashback=0,
                max_cashback=500,
                min_overpayment_allowance_pct=5,
                max_overpayment_allowance_pct=8,
                min_erc_pct=3,
                max_erc_pct=5,
                preferred_rate_type="tracker",
                preferred_initial_period_years=2,
                preferred_repayment_type="capital_repayment",
                portable_preference=1,
                free_valuation_preference=1,
                free_legal_preference=1,
            )
        ),
    ),
    Persona(
        id="incentives-war",
        name="Incentives war",
        tag="fees-cashback",
        description=(
            "Rate and deposit overlap comfortably; the fight is fees, cashback, ERC, and "
            "overpayments — ranges still overlap, but only in a tight commercial band. "
            "Feature prefs are moderate."
        ),
        borrower=BorrowerTerms(
            **_party(
                min_downpayment=55_000,
                max_downpayment=90_000,
                min_interest_rate_pct=4.25,
                max_interest_rate_pct=5.75,
                min_loan_length_years=20,
                max_loan_length_years=30,
                # Overlap with lender on fee: £750–£999
                min_arrangement_fee=0,
                max_arrangement_fee=999,
                # Overlap on cashback: £1,500–£2,000
                min_cashback=1_500,
                max_cashback=4_000,
                # Overlap on overpay: 10–12%
                min_overpayment_allowance_pct=10,
                max_overpayment_allowance_pct=20,
                # Overlap on ERC: 1.5–2.5%
                min_erc_pct=0,
                max_erc_pct=2.5,
                preferred_rate_type="fixed",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=6,
                free_valuation_preference=5,
                free_legal_preference=5,
            )
        ),
        lender=LenderTerms(
            **_party(
                min_downpayment=50_000,
                max_downpayment=100_000,
                min_interest_rate_pct=4.5,
                max_interest_rate_pct=6.0,
                min_loan_length_years=15,
                max_loan_length_years=30,
                min_arrangement_fee=750,
                max_arrangement_fee=1_999,
                min_cashback=0,
                max_cashback=2_000,
                min_overpayment_allowance_pct=5,
                max_overpayment_allowance_pct=12,
                min_erc_pct=1.5,
                max_erc_pct=5,
                preferred_rate_type="discount",
                preferred_initial_period_years=2,
                preferred_repayment_type="capital_repayment",
                portable_preference=4,
                free_valuation_preference=4,
                free_legal_preference=3,
            )
        ),
    ),
    Persona(
        id="features-duel",
        name="Features duel",
        tag="product-features",
        description=(
            "Pricing overlaps easily, but portability / free valuation / free legal are "
            "must-haves for the borrower (10) and almost non-negotiable refusals for the "
            "lender (1). Agents must trade rate or fee to win or concede features."
        ),
        borrower=BorrowerTerms(
            **_party(
                min_downpayment=50_000,
                max_downpayment=100_000,
                min_interest_rate_pct=4.0,
                max_interest_rate_pct=6.0,
                min_loan_length_years=20,
                max_loan_length_years=30,
                min_arrangement_fee=0,
                max_arrangement_fee=1_500,
                min_cashback=0,
                max_cashback=3_000,
                min_overpayment_allowance_pct=5,
                max_overpayment_allowance_pct=15,
                min_erc_pct=0,
                max_erc_pct=4,
                preferred_rate_type="fixed",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=10,
                free_valuation_preference=10,
                free_legal_preference=10,
            )
        ),
        lender=LenderTerms(
            **_party(
                min_downpayment=50_000,
                max_downpayment=100_000,
                min_interest_rate_pct=4.0,
                max_interest_rate_pct=6.0,
                min_loan_length_years=20,
                max_loan_length_years=30,
                min_arrangement_fee=0,
                max_arrangement_fee=1_500,
                min_cashback=0,
                max_cashback=3_000,
                min_overpayment_allowance_pct=5,
                max_overpayment_allowance_pct=15,
                min_erc_pct=0,
                max_erc_pct=4,
                preferred_rate_type="fixed",
                preferred_initial_period_years=5,
                preferred_repayment_type="capital_repayment",
                portable_preference=1,
                free_valuation_preference=1,
                free_legal_preference=1,
            )
        ),
    ),
)


def list_personas() -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "tag": p.tag,
        }
        for p in PERSONAS
    ]


def get_persona(persona_id: str) -> Persona:
    key = persona_id.strip().lower()
    for persona in PERSONAS:
        if persona.id == key:
            return persona
    raise KeyError(persona_id)


def demo_persona() -> Persona:
    return get_persona("demo")
