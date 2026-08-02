import asyncio
from collections.abc import Callable

import typer

from loan_negotiation.cli.intake import collect_borrower_terms, collect_lender_terms
from loan_negotiation.config import settings_with_model
from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms
from loan_negotiation.services.ollama_check import ensure_model_ready
from loan_negotiation.services.results_store import results_json_path
from loan_negotiation.workflow.orchestrator import run_negotiation
from loan_negotiation.workflow.personas import get_persona
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
    print(f"  deposit: £{terms.min_downpayment:,.0f}-£{terms.max_downpayment:,.0f}", flush=True)
    print(
        f"  rate: {terms.min_interest_rate_pct}-{terms.max_interest_rate_pct}%",
        flush=True,
    )
    print(
        f"  term: {terms.min_loan_length_years}-{terms.max_loan_length_years} years",
        flush=True,
    )
    print(
        f"  fee £{terms.min_arrangement_fee:,.0f}-£{terms.max_arrangement_fee:,.0f} | "
        f"cashback £{terms.min_cashback:,.0f}-£{terms.max_cashback:,.0f}",
        flush=True,
    )
    print(
        f"  overpay {terms.min_overpayment_allowance_pct}-{terms.max_overpayment_allowance_pct}% | "
        f"ERC {terms.min_erc_pct}-{terms.max_erc_pct}%",
        flush=True,
    )
    print(
        f"  prefer {terms.preferred_rate_type} / {terms.preferred_initial_period_years}yr / "
        f"{terms.preferred_repayment_type}",
        flush=True,
    )
    print(
        f"  portable={terms.portable_preference}/10 free_val={terms.free_valuation_preference}/10 "
        f"free_legal={terms.free_legal_preference}/10",
        flush=True,
    )


def _print_summary(result) -> None:
    print("\n--- summary ---", flush=True)
    print(f"status: {result.status.value}", flush=True)
    if result.deal:
        d = result.deal
        print("agreed deal:", flush=True)
        print(
            f"  £{d.downpayment:,.0f} deposit | {d.interest_rate_pct}% {d.rate_type} "
            f"({d.initial_period_years}yr) | {d.loan_length_years}yr | {d.repayment_type}",
            flush=True,
        )
        print(
            f"  fee £{d.arrangement_fee:,.0f} | cashback £{d.cashback:,.0f} | "
            f"overpay {d.overpayment_allowance_pct}% | ERC {d.erc_pct}%",
            flush=True,
        )
        print(
            f"  portable={d.portable} free_val={d.free_valuation} free_legal={d.free_legal}",
            flush=True,
        )
        if d.consensus_reached:
            print("  consensus: yes", flush=True)
    if result.scores:
        gap = abs(result.scores.borrower_score - result.scores.lender_score)
        print(
            f"scores: borrower={result.scores.borrower_score:.1f}  "
            f"lender={result.scores.lender_score:.1f}  (gap={gap:.1f})",
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
    persona: str | None = typer.Option(
        None,
        "--persona",
        help="Persona id from the catalog (e.g. demo, features-duel)",
    ),
    attempt: int | None = typer.Option(
        None,
        "--attempt",
        help="Attempt number for eval logging (e.g. 1–3)",
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

    persona_id: str | None = None
    persona_name: str | None = None
    if persona:
        try:
            selected = get_persona(persona)
        except KeyError as exc:
            typer.echo(f"error: unknown persona '{persona}'", err=True)
            raise typer.Exit(code=1) from exc
        borrower = selected.borrower
        lender = selected.lender
        persona_id = selected.id
        persona_name = selected.name
        print(f"Using persona: {selected.name} ({selected.id})\n", flush=True)
    elif demo:
        borrower = sample_borrower()
        lender = sample_lender()
        persona_id = "demo"
        persona_name = "Demo"
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
                persona_id=persona_id,
                persona_name=persona_name,
                attempt=attempt,
                save_interaction=True,
            )
        )
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Logged interaction → {results_json_path()}")
    _print_summary(workflow.result)


if __name__ == "__main__":
    app()
