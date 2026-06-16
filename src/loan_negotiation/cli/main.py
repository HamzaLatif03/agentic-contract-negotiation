import asyncio
from collections.abc import Callable

import typer

from loan_negotiation.cli.intake import collect_borrower_terms, collect_lender_terms
from loan_negotiation.config import settings_with_model
from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms
from loan_negotiation.services.ollama_check import ensure_model_ready
from loan_negotiation.workflow.orchestrator import run_negotiation
from loan_negotiation.workflow.samples import sample_borrower, sample_lender

app = typer.Typer()

MessageHandler = Callable[[str, str, str], None]


def _live_print(stage: str, agent: str, output: str) -> None:
    if stage == "negotiation" and agent == "system":
        print(f"\n{output}", flush=True)
    elif stage == "negotiation":
        print(f"\n  {agent}:", flush=True)
        print(f"  {output}", flush=True)
    else:
        print(f"\n[{stage}] {agent}", flush=True)
        print(output, flush=True)


def _print_terms(title: str, terms: BorrowerTerms | LenderTerms) -> None:
    print(f"\n{title}", flush=True)
    print(
        f"  downpayment: {terms.min_downpayment}-{terms.max_downpayment}",
        flush=True,
    )
    print(
        f"  interest rate: {terms.min_interest_rate_pct}-{terms.max_interest_rate_pct}%",
        flush=True,
    )
    print(
        f"  loan length: {terms.min_loan_length_years}-{terms.max_loan_length_years} years",
        flush=True,
    )
    print(
        f"  fixed preference: {terms.fixed_preference}/10, "
        f"variable preference: {terms.variable_preference}/10",
        flush=True,
    )


def _print_summary(result) -> None:
    print("\n--- summary ---", flush=True)
    print(f"status: {result.status.value}", flush=True)
    if result.deal:
        print("agreed deal:", flush=True)
        print(f"  downpayment: £{result.deal.downpayment:,.0f}", flush=True)
        print(f"  interest rate: {result.deal.interest_rate_pct}%", flush=True)
        print(f"  loan length: {result.deal.loan_length_years} years", flush=True)
        print(f"  interest structure: {result.deal.interest_structure}/10", flush=True)
        if result.deal.consensus_reached:
            print("  consensus: yes", flush=True)
    if result.scores:
        gap = abs(result.scores.borrower_score - result.scores.lender_score)
        print(
            f"scores: borrower={result.scores.borrower_score}  "
            f"lender={result.scores.lender_score}  (gap={gap})",
            flush=True,
        )
    if result.review:
        print(f"reviewer approved: {'yes' if result.review.approved else 'no'}", flush=True)
    if result.llm_metrics:
        m = result.llm_metrics
        ttft = (
            f"{m.time_to_first_token_ms:.0f} ms"
            if m.time_to_first_token_ms is not None
            else "n/a"
        )
        print(
            f"llm: model={m.model}  tokens={m.total_tokens} "
            f"(prompt={m.prompt_tokens}, completion={m.completion_tokens})  "
            f"ttft={ttft}  duration={m.duration_ms:.0f} ms",
            flush=True,
        )
    if result.reasons:
        for reason in result.reasons:
            print(f"note: {reason}", flush=True)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    demo: bool = typer.Option(
        False,
        "--demo",
        help="Use built-in sample borrower/lender data",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Ollama model tag for this run (overrides OLLAMA_MODEL)",
    ),
) -> None:
    """Run the loan agent negotiation workflow."""
    if ctx.invoked_subcommand is not None:
        return

    if demo:
        borrower = sample_borrower()
        lender = sample_lender()
        print("Using demo data.\n", flush=True)
    else:
        print("Enter borrower and lender terms separately.\n", flush=True)
        borrower = collect_borrower_terms()
        lender = collect_lender_terms()

    _print_terms("Borrower starting position", borrower)
    _print_terms("Lender starting position", lender)

    settings = settings_with_model(model)
    print(f"\nModel: {settings.model}\n", flush=True)

    try:
        ensure_model_ready(settings)
        workflow = asyncio.run(
            run_negotiation(
                borrower,
                lender,
                settings=settings,
                on_message=_live_print,
                llm_model=model,
            )
        )
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _print_summary(workflow.result)


if __name__ == "__main__":
    app()
