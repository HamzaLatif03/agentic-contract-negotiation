import typer

from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms, clamp_preference


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


def _prompt_preference(label: str, default: int) -> int:
    typer.echo(f"{label}: 1 = low desire, 10 = high desire")
    while True:
        value = clamp_preference(_prompt_int("  Score (1-10)", default=default))
        return value


def collect_borrower_terms() -> BorrowerTerms:
    typer.echo("\n--- Borrower terms ---")
    fixed = _prompt_preference("How much do you want a fixed rate?", default=8)
    variable = _prompt_preference("How much do you want a variable rate?", default=3)
    return BorrowerTerms(
        min_downpayment=_prompt_float("Minimum downpayment (£)"),
        max_downpayment=_prompt_float("Maximum downpayment (£)"),
        min_interest_rate_pct=_prompt_float("Minimum acceptable interest rate %"),
        max_interest_rate_pct=_prompt_float("Maximum acceptable interest rate %"),
        min_loan_length_years=_prompt_int("Minimum loan length (years)", default=20),
        max_loan_length_years=_prompt_int("Maximum loan length (years)", default=25),
        fixed_preference=fixed,
        variable_preference=variable,
    )


def collect_lender_terms() -> LenderTerms:
    typer.echo("\n--- Lender terms ---")
    fixed = _prompt_preference("How much do you want to offer fixed?", default=2)
    variable = _prompt_preference("How much do you want to offer variable?", default=9)
    return LenderTerms(
        min_downpayment=_prompt_float("Minimum downpayment required (£)"),
        max_downpayment=_prompt_float("Maximum downpayment required (£)"),
        min_interest_rate_pct=_prompt_float("Minimum interest rate %"),
        max_interest_rate_pct=_prompt_float("Maximum interest rate %"),
        min_loan_length_years=_prompt_int("Minimum loan length (years)", default=10),
        max_loan_length_years=_prompt_int("Maximum loan length (years)", default=30),
        fixed_preference=fixed,
        variable_preference=variable,
    )
