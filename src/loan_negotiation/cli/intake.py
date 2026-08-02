import typer

from loan_negotiation.models.loan_terms import (
    INITIAL_PERIODS,
    RATE_TYPES,
    REPAYMENT_TYPES,
    BorrowerTerms,
    LenderTerms,
)
from loan_negotiation.workflow.samples import sample_borrower, sample_lender


def _prompt_float(label: str, default: float | None = None) -> float:
    while True:
        raw = typer.prompt(label, default=str(default) if default is not None else None)
        try:
            return float(raw)
        except ValueError:
            typer.echo("Enter a number.", err=True)


def _prompt_int(label: str, default: int | None = None) -> int:
    while True:
        raw = typer.prompt(label, default=str(default) if default is not None else None)
        try:
            return int(raw)
        except ValueError:
            typer.echo("Enter a whole number.", err=True)


def _prompt_choice(label: str, choices: tuple[str, ...] | tuple[int, ...], default) -> str | int:
    typer.echo(f"{label} — options: {', '.join(str(c) for c in choices)}")
    while True:
        raw = typer.prompt("  Choice", default=str(default))
        if isinstance(choices[0], int):
            try:
                value = int(raw)
            except ValueError:
                typer.echo("Enter a whole number.", err=True)
                continue
            if value in choices:
                return value
        else:
            value = raw.strip().lower()
            if value in choices:
                return value
        typer.echo(f"Choose one of: {', '.join(str(c) for c in choices)}", err=True)


def _collect_party(title: str, defaults) -> dict:
    typer.echo(f"\n--- {title} ---")
    return {
        "min_downpayment": _prompt_float("Min deposit (£)", defaults.min_downpayment),
        "max_downpayment": _prompt_float("Max deposit (£)", defaults.max_downpayment),
        "min_interest_rate_pct": _prompt_float("Min interest rate %", defaults.min_interest_rate_pct),
        "max_interest_rate_pct": _prompt_float("Max interest rate %", defaults.max_interest_rate_pct),
        "min_loan_length_years": _prompt_int("Min loan term (years)", defaults.min_loan_length_years),
        "max_loan_length_years": _prompt_int("Max loan term (years)", defaults.max_loan_length_years),
        "min_arrangement_fee": _prompt_float("Min arrangement fee (£)", defaults.min_arrangement_fee),
        "max_arrangement_fee": _prompt_float("Max arrangement fee (£)", defaults.max_arrangement_fee),
        "min_cashback": _prompt_float("Min cashback (£)", defaults.min_cashback),
        "max_cashback": _prompt_float("Max cashback (£)", defaults.max_cashback),
        "min_overpayment_allowance_pct": _prompt_float(
            "Min overpayment allowance %", defaults.min_overpayment_allowance_pct
        ),
        "max_overpayment_allowance_pct": _prompt_float(
            "Max overpayment allowance %", defaults.max_overpayment_allowance_pct
        ),
        "min_erc_pct": _prompt_float("Min ERC %", defaults.min_erc_pct),
        "max_erc_pct": _prompt_float("Max ERC %", defaults.max_erc_pct),
        "preferred_rate_type": _prompt_choice(
            "Preferred rate type", RATE_TYPES, defaults.preferred_rate_type
        ),
        "preferred_initial_period_years": _prompt_choice(
            "Preferred initial deal period (years)",
            INITIAL_PERIODS,
            defaults.preferred_initial_period_years,
        ),
        "preferred_repayment_type": _prompt_choice(
            "Preferred repayment type", REPAYMENT_TYPES, defaults.preferred_repayment_type
        ),
        "portable_preference": _prompt_int(
            "Portability desire 1-10 (1=off, 5=flex, 10=on)", defaults.portable_preference
        ),
        "free_valuation_preference": _prompt_int(
            "Free valuation desire 1-10", defaults.free_valuation_preference
        ),
        "free_legal_preference": _prompt_int(
            "Free legal desire 1-10", defaults.free_legal_preference
        ),
    }


def collect_borrower_terms() -> BorrowerTerms:
    return BorrowerTerms(**_collect_party("Borrower terms", sample_borrower()))


def collect_lender_terms() -> LenderTerms:
    return LenderTerms(**_collect_party("Lender terms", sample_lender()))
