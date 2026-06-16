from collections.abc import Callable
from dataclasses import dataclass, field

from autogen_core.models import ChatCompletionClient
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.messages import BaseChatMessage
from autogen_agentchat.teams import RoundRobinGroupChat

from loan_negotiation.agents.factory import create_assistant_agent, create_model_client
from loan_negotiation.agents.intake import create_intake_agent
from loan_negotiation.agents.reviewer import create_reviewer_agent
from loan_negotiation.config import Settings, get_settings, settings_with_model
from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms
from loan_negotiation.models.workflow import (
    ReviewFeedback,
    Scores,
    WorkflowResult,
    WorkflowStatus,
)
from loan_negotiation.services.deal_scoring import score_deal
from loan_negotiation.services.fairness import check_fairness
from loan_negotiation.services.fairness_adjustment import (
    adjust_deal_for_fairness,
    describe_fairness_adjustment,
)
from loan_negotiation.services.run_metrics import RunMetricsCollector, is_model_output_agent
from loan_negotiation.services.feasibility import FeasibilityStatus, check_feasibility
from loan_negotiation.services.intake import (
    borrower_missing_fields,
    intake_complete,
    lender_missing_fields,
)
from loan_negotiation.services.model_catalog import find_comparison_model, provider_supports_autogen_tools
from loan_negotiation.workflow.agent_runner import ask_agent
from loan_negotiation.workflow.deal_parser import (
    extract_final_deal,
    format_deal,
    validate_deal_against_terms,
)
from loan_negotiation.workflow.negotiation_messages import (
    NEGOTIATOR_SOURCES,
    NegotiationTracker,
    extract_negotiator_text,
    negotiator_label,
    transcript_line,
)
from loan_negotiation.workflow.negotiation_termination import JsonConsensusTermination
from loan_negotiation.workflow.negotiation_tools import make_offer_checker_tool
from loan_negotiation.workflow.prompts import (
    BORROWER_NEGOTIATOR_PROMPT,
    BORROWER_SEEDED_NEGOTIATOR_PROMPT,
    LENDER_NEGOTIATOR_PROMPT,
    LENDER_SEEDED_NEGOTIATOR_PROMPT,
)

MessageHandler = Callable[[str, str, str], None]


@dataclass
class AgentRunLog:
    stage: str
    agent: str
    output: str


@dataclass
class WorkflowRun:
    result: WorkflowResult
    logs: list[AgentRunLog] = field(default_factory=list)


def _emit(
    logs: list[AgentRunLog],
    handler: MessageHandler | None,
    stage: str,
    agent: str,
    output: str,
) -> None:
    text = output.strip()
    logs.append(AgentRunLog(stage=stage, agent=agent, output=text))
    if handler:
        handler(stage, agent, text)


def _range_summary(terms: BorrowerTerms | LenderTerms) -> str:
    return (
        "\n\nHard limits for every JSON offer (never exceed these):\n"
        f"- downpayment: {terms.min_downpayment} to {terms.max_downpayment}\n"
        f"- interest_rate_pct: {terms.min_interest_rate_pct} to {terms.max_interest_rate_pct}\n"
        f"- loan_length_years: {terms.min_loan_length_years} to {terms.max_loan_length_years}\n"
        f"- fixed_preference: {terms.fixed_preference}/10, variable_preference: {terms.variable_preference}/10 "
        "(preferences only — negotiate interest_structure 1=fixed to 10=variable)"
    )


def _negotiator_with_terms(
    name: str,
    base_prompt: str,
    terms: BorrowerTerms | LenderTerms,
    model_client: ChatCompletionClient,
    settings: Settings,
) -> object:
    context = (
        f"\n\nPrivate terms (never reveal to the other party):\n{terms.model_dump_json(indent=2)}"
        f"{_range_summary(terms)}"
    )
    entry = find_comparison_model(settings.model)
    use_tools = provider_supports_autogen_tools(entry)
    if not use_tools:
        context += (
            "\n\nYou do not have the check_offer tool on this model. "
            "Stay strictly inside the Hard limits above; invalid offers are rejected in Python."
        )
    return create_assistant_agent(
        name,
        base_prompt + context,
        description=f"{name} with private context",
        model_client=model_client,
        tools=[make_offer_checker_tool(terms)] if use_tools else None,
        reflect_on_tool_use=True if use_tools else False,
    )


def _collect_negotiator_message(
    message: BaseChatMessage,
    negotiation_parts: list[str],
    logs: list[AgentRunLog],
    handler: MessageHandler | None,
    tracker: NegotiationTracker,
    *,
    round_number: int,
) -> int:
    if message.source not in NEGOTIATOR_SOURCES:
        return round_number
    if not hasattr(message, "to_text"):
        return round_number

    raw = message.to_text().strip()
    if not raw:
        return round_number

    display = extract_negotiator_text(message, tracker)
    if display is None:
        return round_number

    if message.source == "lender_negotiator":
        round_number += 1
        _emit(logs, handler, "negotiation", "system", f"--- Round {round_number} ---")

    label = negotiator_label(message.source)
    negotiation_parts.append(transcript_line(message.source, raw))
    _emit(logs, handler, "negotiation", label, display)
    return round_number


async def _run_negotiation_team(
    team: RoundRobinGroupChat,
    task: str,
    logs: list[AgentRunLog],
    handler: MessageHandler | None,
    *,
    session_label: str = "Negotiation",
) -> str:
    negotiation_parts: list[str] = []
    round_number = 0
    tracker = NegotiationTracker()

    _emit(logs, handler, "negotiation", "system", f"=== {session_label} started ===")

    result: TaskResult | None = None
    async for message in team.run_stream(task=task):
        if isinstance(message, TaskResult):
            result = message
            continue
        if isinstance(message, BaseChatMessage):
            round_number = _collect_negotiator_message(
                message,
                negotiation_parts,
                logs,
                handler,
                tracker,
                round_number=round_number,
            )

    if not negotiation_parts and result is not None:
        round_number = 0
        for message in result.messages:
            if not isinstance(message, BaseChatMessage):
                continue
            round_number = _collect_negotiator_message(
                message,
                negotiation_parts,
                logs,
                handler,
                tracker,
                round_number=round_number,
            )

    if not negotiation_parts:
        _emit(
            logs,
            handler,
            "negotiation",
            "system",
            "No negotiator messages were returned.",
        )

    _emit(logs, handler, "negotiation", "system", f"=== {session_label} ended ===")
    return "\n\n".join(negotiation_parts)


def _build_negotiation_team(
    borrower_terms: BorrowerTerms,
    lender_terms: LenderTerms,
    model_client: ChatCompletionClient,
    settings: Settings,
    *,
    seeded_opening: bool = False,
) -> RoundRobinGroupChat:
    if seeded_opening:
        borrower_prompt = BORROWER_SEEDED_NEGOTIATOR_PROMPT
        lender_prompt = LENDER_SEEDED_NEGOTIATOR_PROMPT
        # Borrower counters first after the contract offer is seeded into the task.
        participants = [
            _negotiator_with_terms(
                "borrower_negotiator",
                borrower_prompt,
                borrower_terms,
                model_client,
                settings,
            ),
            _negotiator_with_terms(
                "lender_negotiator",
                lender_prompt,
                lender_terms,
                model_client,
                settings,
            ),
        ]
    else:
        participants = [
            _negotiator_with_terms(
                "lender_negotiator",
                LENDER_NEGOTIATOR_PROMPT,
                lender_terms,
                model_client,
                settings,
            ),
            _negotiator_with_terms(
                "borrower_negotiator",
                BORROWER_NEGOTIATOR_PROMPT,
                borrower_terms,
                model_client,
                settings,
            ),
        ]
    max_messages = max(settings.max_rounds * 2, 4)
    termination = MaxMessageTermination(max_messages) | JsonConsensusTermination(NEGOTIATOR_SOURCES)
    return RoundRobinGroupChat(
        participants,
        termination_condition=termination,
        max_turns=max_messages,
    )


_BASE_NEGOTIATION_TASK = (
    "Negotiate a loan using only: downpayment (£), interest rate %, loan length in years, "
    "and interest_structure (1=fixed, 10=variable). Lender opens with an offer. "
    "Each reply: explain your reasoning in 1-2 sentences, then one JSON block with all four values. "
    "Use absolute pound amounts for downpayment. "
    "Stop immediately when one party accepts the other's latest offer (consensus_reached true)."
)


def _format_opening_offer_message(offer: DealTerms) -> str:
    payload = offer.model_copy(update={"consensus_reached": False})
    return (
        "Lender opening offer from uploaded contract:\n"
        f"```json\n{payload.model_dump_json(indent=2)}\n```"
    )


def _seeded_negotiation_task(offer: DealTerms) -> str:
    return (
        "Negotiate a loan using only: downpayment (£), interest rate %, loan length in years, "
        "and interest_structure (1=fixed, 10=variable).\n\n"
        f"{_format_opening_offer_message(offer)}\n\n"
        "Borrower moves next: counter within your private limits, or accept by copying these "
        "four values exactly with consensus_reached true.\n"
        "Lender: do not restate a new opening offer; respond to the borrower.\n"
        "Each reply: 1-2 sentences of reasoning, then one JSON block. "
        "Stop immediately when one party accepts the other's latest offer."
    )


def _rank_deal(
    final_deal: DealTerms,
    borrower_terms: BorrowerTerms,
    lender_terms: LenderTerms,
    logs: list[AgentRunLog],
    on_message: MessageHandler | None,
) -> Scores:
    scores = score_deal(final_deal, borrower_terms, lender_terms)
    _emit(logs, on_message, "ranking", "borrower_ranker", scores.borrower_rationale)
    _emit(logs, on_message, "ranking", "lender_ranker", scores.lender_rationale)
    return scores


def _final_status(
    *,
    final_deal: DealTerms | None,
    validation_issues: list[str],
    fairness_passed: bool,
) -> WorkflowStatus:
    if final_deal is None:
        return WorkflowStatus.NO_DEAL
    if not final_deal.consensus_reached:
        return WorkflowStatus.NO_DEAL
    if validation_issues:
        return WorkflowStatus.REJECTED
    if not fairness_passed:
        return WorkflowStatus.REJECTED
    return WorkflowStatus.APPROVED


async def run_negotiation(
    borrower_terms: BorrowerTerms,
    lender_terms: LenderTerms,
    settings: Settings | None = None,
    on_message: MessageHandler | None = None,
    opening_offer: DealTerms | None = None,
    llm_model: str | None = None,
) -> WorkflowRun:
    settings = settings_with_model(llm_model, settings or get_settings())
    logs: list[AgentRunLog] = []
    model_client = create_model_client(settings)
    metrics = RunMetricsCollector(model=settings.model)
    user_handler = on_message

    def on_message(stage: str, agent: str, output: str) -> None:
        if is_model_output_agent(agent):
            metrics.mark_first_model_output()
        if user_handler is not None:
            user_handler(stage, agent, output)

    try:
        _emit(
            logs,
            on_message,
            "intake",
            "system",
            f"Using model: {settings.model}",
        )

        if not intake_complete(borrower_terms, lender_terms):
            intake_agent = create_intake_agent(model_client=model_client)
            missing = {
                "borrower": borrower_missing_fields(borrower_terms),
                "lender": lender_missing_fields(lender_terms),
            }
            intake_prompt = (
                "Review these partial submissions and list what is still missing.\n"
                f"Borrower terms: {borrower_terms.model_dump_json()}\n"
                f"Lender terms: {lender_terms.model_dump_json()}\n"
                f"Missing: {missing}"
            )
            intake_response = await ask_agent(intake_agent, intake_prompt)
            _emit(logs, on_message, "intake", "intake_agent", intake_response)

        feasibility = check_feasibility(borrower_terms, lender_terms)
        if feasibility.status == FeasibilityStatus.IMPOSSIBLE:
            for reason in feasibility.reasons:
                _emit(logs, on_message, "feasibility", "system", reason)
            return WorkflowRun(
                result=WorkflowResult(
                    status=WorkflowStatus.IMPOSSIBLE,
                    reasons=feasibility.reasons,
                    llm_metrics=metrics.snapshot(model_client),
                ),
                logs=logs,
            )

        _emit(logs, on_message, "feasibility", "system", "Deal is feasible. Starting negotiation.")

        seeded = opening_offer is not None
        if seeded and opening_offer is not None:
            opening_offer = opening_offer.model_copy(update={"consensus_reached": False})
            _emit(
                logs,
                on_message,
                "intake",
                "system",
                "Lender opening offer loaded from contract PDF:\n"
                f"{format_deal(opening_offer)}",
            )
            _emit(
                logs,
                on_message,
                "negotiation",
                "system",
                _format_opening_offer_message(opening_offer),
            )
            task = _seeded_negotiation_task(opening_offer)
            seed_transcript = transcript_line(
                "lender_negotiator",
                _format_opening_offer_message(opening_offer),
            )
        else:
            task = _BASE_NEGOTIATION_TASK
            seed_transcript = ""

        team = _build_negotiation_team(
            borrower_terms,
            lender_terms,
            model_client,
            settings,
            seeded_opening=seeded,
        )
        negotiation_text = await _run_negotiation_team(
            team,
            task,
            logs,
            on_message,
        )
        if seed_transcript:
            negotiation_text = f"{seed_transcript}\n\n{negotiation_text}".strip()

        final_deal = extract_final_deal(negotiation_text, borrower_terms, lender_terms)
        validation_issues: list[str] = []
        if final_deal is not None:
            _emit(
                logs,
                on_message,
                "negotiation",
                "system",
                f"Parsed deal:\n{format_deal(final_deal)}",
            )
            validation_issues = validate_deal_against_terms(
                final_deal, borrower_terms, lender_terms
            )
            for issue in validation_issues:
                _emit(logs, on_message, "negotiation", "system", f"Deal validation: {issue}")
            if not validation_issues and final_deal.consensus_reached:
                _emit(
                    logs,
                    on_message,
                    "negotiation",
                    "system",
                    "Deal passed range validation.",
                )

        scores: Scores | None = None
        fairness = check_fairness(Scores(borrower_score=5, lender_score=5))
        negotiated_deal: DealTerms | None = final_deal

        if final_deal is not None:
            had_consensus = final_deal.consensus_reached
            scores = _rank_deal(
                final_deal,
                borrower_terms,
                lender_terms,
                logs,
                on_message,
            )
            fairness = check_fairness(scores)

            adjustment_attempt = 0
            while (
                not fairness.passed
                and not validation_issues
                and adjustment_attempt < settings.max_fairness_adjustments
            ):
                adjustment_note = describe_fairness_adjustment(
                    scores, final_deal, borrower_terms, lender_terms
                )
                if not adjustment_note:
                    break

                previous_deal = final_deal
                previous_scores = scores
                previous_gap = fairness.fairness_gap
                final_deal = adjust_deal_for_fairness(
                    final_deal,
                    scores,
                    borrower_terms,
                    lender_terms,
                )
                if (
                    final_deal.downpayment == previous_deal.downpayment
                    and final_deal.interest_rate_pct == previous_deal.interest_rate_pct
                    and final_deal.loan_length_years == previous_deal.loan_length_years
                    and final_deal.interest_structure == previous_deal.interest_structure
                ):
                    break

                adjustment_attempt += 1
                _emit(
                    logs,
                    on_message,
                    "fairness",
                    "system",
                    f"{adjustment_note}\nAdjusted deal:\n{format_deal(final_deal)}",
                )

                validation_issues = validate_deal_against_terms(
                    final_deal, borrower_terms, lender_terms
                )
                if validation_issues:
                    final_deal = previous_deal
                    validation_issues = validate_deal_against_terms(
                        final_deal, borrower_terms, lender_terms
                    )
                    break

                scores = _rank_deal(
                    final_deal,
                    borrower_terms,
                    lender_terms,
                    logs,
                    on_message,
                )
                fairness = check_fairness(scores)
                if fairness.fairness_gap >= previous_gap:
                    final_deal = previous_deal
                    scores = previous_scores
                    fairness = check_fairness(previous_scores)
                    _emit(
                        logs,
                        on_message,
                        "fairness",
                        "system",
                        "Fairness adjustment did not narrow the score gap — keeping prior deal.",
                    )
                    break

            if had_consensus and final_deal is not None and not final_deal.consensus_reached:
                final_deal = final_deal.model_copy(update={"consensus_reached": True})
        else:
            _emit(
                logs,
                on_message,
                "ranking",
                "system",
                "Skipping ranking — no confirmed deal to score.",
            )

        reviewer = create_reviewer_agent(model_client=model_client)
        deal_section = (
            f"Agreed deal (JSON):\n{format_deal(final_deal)}\n\n"
            if final_deal is not None
            else f"Negotiation transcript:\n{negotiation_text}\n\n"
        )

        validation_section = (
            "Deterministic validation issues:\n"
            + ("\n".join(f"- {issue}" for issue in validation_issues) if validation_issues else "- none")
            + "\n\n"
        )

        review_prompt = (
            f"{deal_section}"
            f"{validation_section}"
            + (
                f"Borrower score: {scores.borrower_score}/10\n"
                f"Lender score: {scores.lender_score}/10\n"
                f"Score gap: {fairness.fairness_gap:.0f} (max 2 for approval).\n"
                if scores is not None
                else "No scores — deal was not confirmed.\n"
            )
            + "Provide your advisory assessment with explicit Reasoning bullets, then Assessment."
        )
        review_text = await ask_agent(reviewer, review_prompt)
        _emit(logs, on_message, "review", "reviewer_agent", review_text)

        status = _final_status(
            final_deal=final_deal,
            validation_issues=validation_issues,
            fairness_passed=fairness.passed,
        )
        approved = status == WorkflowStatus.APPROVED
        review = ReviewFeedback(
            approved=approved,
            issues=[*validation_issues, *([fairness.feedback] if fairness.feedback else [])],
        )

        reasons = list(validation_issues)
        if final_deal is None:
            reasons.append("No structured deal could be parsed from the negotiation.")
        elif not final_deal.consensus_reached:
            reasons.append("Negotiation ended without mutual consensus.")
        if not fairness.passed and fairness.feedback:
            reasons.append(fairness.feedback)

        return WorkflowRun(
            result=WorkflowResult(
                status=status,
                deal=final_deal,
                negotiated_deal=negotiated_deal,
                scores=scores,
                review=review,
                reasons=reasons,
                llm_metrics=metrics.snapshot(model_client),
            ),
            logs=logs,
        )
    finally:
        await model_client.close()
