from collections.abc import Callable
from dataclasses import dataclass, field
import re

from autogen_core.models import ChatCompletionClient
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.messages import BaseChatMessage
from autogen_agentchat.teams import RoundRobinGroupChat

from loan_negotiation.agents.factory import ask_agent, create_assistant_agent, create_model_client
from loan_negotiation.agents.party_wall_agent import PartyWallAssistantAgent
from loan_negotiation.config import Settings, get_settings, settings_with_model
from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms
from loan_negotiation.models.workflow import (
    ReviewFeedback,
    Scores,
    WorkflowResult,
    WorkflowStatus,
)
from loan_negotiation.services.deal_scoring import score_deal
from loan_negotiation.services.fairness_adjustment import (
    adjust_deal_for_fairness,
    check_fairness,
    close_deal_via_fairness,
    describe_fairness_adjustment,
)
from loan_negotiation.workflow.negotiation_state import deals_match
from loan_negotiation.services.run_metrics import RunMetricsCollector, is_model_output_agent
from loan_negotiation.services.feasibility import FeasibilityStatus, check_feasibility
from loan_negotiation.services.intake import (
    borrower_missing_fields,
    intake_complete,
    lender_missing_fields,
)
from loan_negotiation.services.model_catalog import find_comparison_model, provider_supports_autogen_tools
from loan_negotiation.services.limit_compensation import (
    evaluate_deal_limits,
    party_within_hard_limits,
)
from loan_negotiation.services.limit_repair import repair_clears_limit_issues
from loan_negotiation.services.results_store import append_interaction
from loan_negotiation.workflow.deal_parser import (
    extract_final_deal,
    format_deal,
    parse_offer_from_text,
    parse_offer_from_text_lenient,
)
from loan_negotiation.workflow.fight_targets import fight_targets_summary
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
    INTAKE_AGENT_PROMPT,
    LENDER_NEGOTIATOR_PROMPT,
    LENDER_SEEDED_NEGOTIATOR_PROMPT,
    REVIEWER_AGENT_PROMPT,
)
from loan_negotiation.workflow.wall_enforcement import enforce_party_walls_in_message
from loan_negotiation.services.opening_offer import (
    OpeningOfferExtractionError,
    extract_opening_offer_with_local_llama,
    format_opening_offer_announcement,
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
        "\n\nHARD PRIVATE WALLS — every JSON offer MUST stay inside these inclusive bounds.\n"
        "Python clamps any field that leaves these walls. Do not propose outside them.\n"
        f"- deposit (downpayment £): {terms.min_downpayment:g} to {terms.max_downpayment:g} "
        f"(NEVER below {terms.min_downpayment:g}, NEVER above {terms.max_downpayment:g})\n"
        f"- interest_rate_pct: {terms.min_interest_rate_pct:g} to {terms.max_interest_rate_pct:g}\n"
        f"- loan_length_years: {terms.min_loan_length_years} to {terms.max_loan_length_years}\n"
        f"- arrangement_fee £: {terms.min_arrangement_fee:g} to {terms.max_arrangement_fee:g}\n"
        f"- cashback £: {terms.min_cashback:g} to {terms.max_cashback:g}\n"
        f"- overpayment_allowance_pct: {terms.min_overpayment_allowance_pct:g} to "
        f"{terms.max_overpayment_allowance_pct:g}\n"
        f"- erc_pct: {terms.min_erc_pct:g} to {terms.max_erc_pct:g}\n"
        f"- preferred rate_type: {terms.preferred_rate_type}\n"
        f"- preferred initial_period_years: {terms.preferred_initial_period_years}\n"
        f"- preferred repayment_type: {terms.preferred_repayment_type}\n"
        f"- portable_preference (1=off … 10=on): {terms.portable_preference}\n"
        f"- free_valuation_preference: {terms.free_valuation_preference}\n"
        f"- free_legal_preference: {terms.free_legal_preference}\n"
        "If the other party proposes outside YOUR walls, do NOT copy those numbers — "
        "counter with values inside YOUR walls and call the offending term non-negotiable.\n"
        "You may never accept (consensus_reached true) a package that breaks YOUR walls.\n"
        "- When holding a wall in conversation, say it is non-negotiable / as far as you will go — "
        "never mention limits, ranges, or mins/maxes.\n"
        "- Always read the other party's latest reasons and answer them in your next counter.\n"
        "- Trade preferences only: concede features where your preference is ≤4 to protect "
        "rate/fee or features scored ≥8."
        f"{fight_targets_summary(terms)}"
    )


def _negotiator_with_terms(
    name: str,
    base_prompt: str,
    terms: BorrowerTerms | LenderTerms,
    model_client: ChatCompletionClient,
    settings: Settings,
) -> PartyWallAssistantAgent:
    context = (
        f"\n\nPrivate terms (never reveal to the other party):\n{terms.model_dump_json(indent=2)}"
        f"{_range_summary(terms)}"
    )
    entry = find_comparison_model(settings.model)
    use_tools = provider_supports_autogen_tools(entry)
    if not use_tools:
        context += (
            "\n\nYou do not have the check_offer tool on this model. "
            "Do NOT emit <tool_call>, function calls, or XML tool markup. "
            "Stay inside the private walls above on EVERY offer — no exceptions. "
            "Out-of-wall numbers are clamped in Python before the other side sees them. "
            "In spoken replies never say hard/soft limit — say non-negotiable. "
            "Read and answer the other party's latest reasons each round. "
            "Every reply must include 1-2 commercial sentences (no 'Reasoning:' label) "
            "plus the JSON block."
        )
    return PartyWallAssistantAgent(
        name,
        party_terms=terms,
        model_client=model_client,
        system_message=base_prompt + context,
        description=f"{name} with private context",
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
    terms_by_source: dict[str, BorrowerTerms | LenderTerms] | None = None,
) -> int:
    if message.source not in NEGOTIATOR_SOURCES:
        return round_number
    if not hasattr(message, "to_text"):
        return round_number

    raw = message.to_text().strip()
    if not raw:
        return round_number

    wall_notes: list[str] = []
    if terms_by_source and message.source in terms_by_source:
        clamped_raw, wall_notes = enforce_party_walls_in_message(
            raw, terms_by_source[message.source]
        )
        if wall_notes:
            raw = clamped_raw
            _emit(
                logs,
                handler,
                "negotiation",
                "system",
                "Wall enforcement: adjusted this party's offer into their private bounds "
                "(illegal fields were not published to the counterpart).",
            )

    display = extract_negotiator_text(message, tracker)
    if wall_notes:
        from loan_negotiation.workflow.negotiation_messages import format_deal_line

        offer = parse_offer_from_text(raw) or parse_offer_from_text_lenient(raw)
        prose = raw.split("```", 1)[0].strip() if "```" in raw else raw
        if offer is not None:
            display = (
                f"{prose}\nOffering: {format_deal_line(offer)}".strip()
                if prose
                else format_deal_line(offer)
            )
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
    terms_by_source: dict[str, BorrowerTerms | LenderTerms] | None = None,
) -> tuple[str, int]:
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
                terms_by_source=terms_by_source,
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
                terms_by_source=terms_by_source,
            )

    if not negotiation_parts:
        _emit(
            logs,
            handler,
            "negotiation",
            "system",
            "No negotiator messages were returned.",
        )

    _emit(
        logs,
        handler,
        "negotiation",
        "system",
        f"=== {session_label} ended after {round_number} round(s) ===",
    )
    return "\n\n".join(negotiation_parts), round_number


def _build_negotiation_team(
    borrower_terms: BorrowerTerms,
    lender_terms: LenderTerms,
    model_client: ChatCompletionClient,
    settings: Settings,
    *,
    seeded_opening: bool = False,
    rounds_budget: int | None = None,
) -> RoundRobinGroupChat:
    # Seeded: borrower counters first. Unseeded: lender opens.
    order = (
        (
            ("borrower_negotiator", BORROWER_SEEDED_NEGOTIATOR_PROMPT, borrower_terms),
            ("lender_negotiator", LENDER_SEEDED_NEGOTIATOR_PROMPT, lender_terms),
        )
        if seeded_opening
        else (
            ("lender_negotiator", LENDER_NEGOTIATOR_PROMPT, lender_terms),
            ("borrower_negotiator", BORROWER_NEGOTIATOR_PROMPT, borrower_terms),
        )
    )
    participants = [
        _negotiator_with_terms(name, prompt, terms, model_client, settings)
        for name, prompt, terms in order
    ]
    budget = rounds_budget if rounds_budget is not None else settings.max_rounds
    max_messages = max(max(budget, 1) * 2, 4)
    termination = MaxMessageTermination(max_messages) | JsonConsensusTermination(NEGOTIATOR_SOURCES)
    return RoundRobinGroupChat(
        participants,
        termination_condition=termination,
        max_turns=max_messages,
    )


def _negotiator_terms_by_source(
    borrower_terms: BorrowerTerms,
    lender_terms: LenderTerms,
) -> dict[str, BorrowerTerms | LenderTerms]:
    return {
        "borrower_negotiator": borrower_terms,
        "lender_negotiator": lender_terms,
    }


_BASE_NEGOTIATION_TASK = (
    "Negotiate a UK residential mortgage package (deposit, rate, term, rate type, "
    "initial deal period, fees, cashback, overpayments, ERC, repayment type, "
    "portability, free valuation, free legal). "
    "Lender opens FIRST with a strong bank-side package near the lender's targets — "
    "do not imply knowledge of borrower limits or prefs. "
    "Borrower must COUNTER with a different package toward borrower targets "
    "(never copy the lender's JSON unless accepting with consensus_reached true). "
    "Every later reply: read the other party's latest commercial reasons and respond to them "
    "in prose and in the JSON numbers. "
    "When holding a term, call it non-negotiable — never say hard limit / range / min-max. "
    "Every reply: 1-2 commercial sentences (do NOT prefix with 'Reasoning:'), "
    "then one JSON block with all deal fields. JSON-only replies are not allowed. "
    "Use absolute pound amounts for deposit/fees/cashback. "
    "Fight for your side over multiple rounds. "
    "Stop immediately when one party accepts the other's latest offer (consensus_reached true)."
)


def _seeded_negotiation_task(offer: DealTerms) -> str:
    return (
        "Negotiate a UK residential mortgage package "
        "(deposit, rate, term, product features, fees and incentives).\n\n"
        f"{format_opening_offer_announcement(offer)}\n\n"
        "Borrower moves next: COUNTER toward your targets by changing at least "
        "2 fields (deposit/fee/rate/cashback). Do not paste this opening unchanged "
        "unless you are accepting with consensus_reached true.\n"
        "Lender: do not restate a new opening offer; respond to the borrower's stated reasons.\n"
        "Every reply: read the other side's latest prose, answer it, then one JSON block. "
        "When holding a term, say non-negotiable — never say hard limit. "
        "Stop immediately when one party accepts the other's latest offer."
    )


def _neutral_validation_hints(issues: list[str]) -> list[str]:
    """Describe invalid fields without naming which party's private limit was hit."""
    hints: list[str] = []
    for issue in issues:
        low = issue.lower()
        if "downpayment" in low or "deposit" in low:
            hints.append("deposit must move into a mutually acceptable band")
        elif "interest rate" in low:
            hints.append("interest rate must move into a mutually acceptable band")
        elif "loan length" in low or "loan term" in low:
            hints.append("loan term must move into a mutually acceptable band")
        elif "arrangement fee" in low:
            hints.append("arrangement fee must move into a mutually acceptable band")
        elif "cashback" in low:
            hints.append("cashback must move into a mutually acceptable band")
        elif "overpayment" in low:
            hints.append("overpayment allowance must move into a mutually acceptable band")
        elif "erc" in low:
            hints.append("ERC must move into a mutually acceptable band")
        else:
            hints.append("one or more terms are outside the mutually acceptable band")
    # Preserve order, drop duplicates.
    return list(dict.fromkeys(hints))


def _parse_ratification_decision(text: str) -> bool | None:
    """Parse ACCEPT/REJECT from a middleman ratification reply."""
    match = re.search(r"DECISION\s*:\s*(ACCEPT|REJECT)\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper() == "ACCEPT"
    upper = text.upper()
    has_accept = bool(re.search(r"\bACCEPT\b", upper))
    has_reject = bool(re.search(r"\bREJECT\b", upper))
    if has_accept and not has_reject:
        return True
    if has_reject and not has_accept:
        return False
    return None


def _ratification_walls_context(terms: BorrowerTerms | LenderTerms) -> str:
    """Numeric hard walls only — no fight targets / preference pressure."""
    return (
        "Hard numeric walls for this ratification (inclusive):\n"
        f"- deposit £: {terms.min_downpayment:g}–{terms.max_downpayment:g}\n"
        f"- interest rate %: {terms.min_interest_rate_pct:g}–{terms.max_interest_rate_pct:g}\n"
        f"- loan term years: {terms.min_loan_length_years}–{terms.max_loan_length_years}\n"
        f"- arrangement fee £: {terms.min_arrangement_fee:g}–{terms.max_arrangement_fee:g}\n"
        f"- cashback £: {terms.min_cashback:g}–{terms.max_cashback:g}\n"
        f"- overpayment %: {terms.min_overpayment_allowance_pct:g}–"
        f"{terms.max_overpayment_allowance_pct:g}\n"
        f"- ERC %: {terms.min_erc_pct:g}–{terms.max_erc_pct:g}\n"
        "Rate type, initial period, and freebies are commercial compromises — "
        "NOT grounds to reject if every numeric field above is inside your walls."
    )


def _middleman_ratification_prompt(package: DealTerms, *, party: str) -> str:
    return (
        f"A middleman fairness agent has ironed out this final mortgage package "
        f"(already balanced inside both parties' overlapping numeric walls):\n"
        f"{format_deal(package)}\n\n"
        f"You are the {party}. This is ratification of a closing package — not a new negotiation.\n"
        "Decision rule (strict):\n"
        "- If EVERY numeric field (deposit, rate, term, fee, cashback, overpay, ERC) is inside "
        "YOUR hard walls above → you MUST answer DECISION: ACCEPT.\n"
        "- Preference mismatches (fixed vs tracker, free valuation, portable, etc.) are normal "
        "in a middleman compromise — they are NOT a reason to reject.\n"
        "- REJECT only if a numeric field is clearly outside your hard walls.\n"
        "- Do NOT propose a counter-offer or change any numbers.\n"
        "- Do NOT invent walls that are not listed (there is no 'rate_type wall').\n"
        "- One short commercial sentence, then exactly one line:\n"
        "  DECISION: ACCEPT\n"
        "  or\n"
        "  DECISION: REJECT"
    )


def _effective_ratification(
    *,
    party: str,
    package: DealTerms,
    terms: BorrowerTerms | LenderTerms,
    llm_decision: bool | None,
    logs: list[AgentRunLog],
    on_message: MessageHandler | None,
) -> bool:
    """
    Walls decide. Preference-only REJECT from the LLM is overridden to ACCEPT when
    the package is inside this party's hard numeric walls.
    """
    walls_ok, _, _ = party_within_hard_limits(terms, package)
    if walls_ok:
        if llm_decision is False:
            _emit(
                logs,
                on_message,
                "fairness",
                "fairness_agent",
                f"{party.capitalize()} rejected on preferences/comfort, but the package is "
                "inside their hard numeric walls — treating as ACCEPT.",
            )
        elif llm_decision is None:
            _emit(
                logs,
                on_message,
                "fairness",
                "fairness_agent",
                f"{party.capitalize()} reply unclear; package inside hard walls — "
                "treating as ACCEPT.",
            )
        return True

    _emit(
        logs,
        on_message,
        "fairness",
        "fairness_agent",
        f"{party.capitalize()} correctly cannot ratify — package outside their hard walls.",
    )
    return False


async def _ratify_middleman_package(
    *,
    package: DealTerms,
    borrower_terms: BorrowerTerms,
    lender_terms: LenderTerms,
    model_client: ChatCompletionClient,
    settings: Settings,
    logs: list[AgentRunLog],
    on_message: MessageHandler | None,
) -> tuple[bool, str]:
    """
    Present the middleman package once to each side (2 LLM calls, no renegotiation).

    Acceptance is governed by hard numeric walls: preference-only rejects are overridden.
    Returns (both_accepted, summary_note).
    """
    _emit(
        logs,
        on_message,
        "fairness",
        "fairness_agent",
        "Middleman package ready for ratification (accept/reject only — no renegotiation):\n"
        f"{format_deal(package)}",
    )

    lender = create_assistant_agent(
        "lender_ratifier",
        (
            "You ratify a middleman closing package for the lender. "
            "ACCEPT when all numeric fields are inside your hard walls; "
            "do not reject for rate-type or freebie preferences.\n"
            f"{_ratification_walls_context(lender_terms)}"
        ),
        description="Lender ratification of middleman package",
        model_client=model_client,
        settings=settings,
    )
    borrower = create_assistant_agent(
        "borrower_ratifier",
        (
            "You ratify a middleman closing package for the borrower. "
            "ACCEPT when all numeric fields are inside your hard walls; "
            "do not reject for rate-type or freebie preferences.\n"
            f"{_ratification_walls_context(borrower_terms)}"
        ),
        description="Borrower ratification of middleman package",
        model_client=model_client,
        settings=settings,
    )

    lender_text = await ask_agent(
        lender, _middleman_ratification_prompt(package, party="lender")
    )
    _emit(logs, on_message, "negotiation", "lender", lender_text)
    borrower_text = await ask_agent(
        borrower, _middleman_ratification_prompt(package, party="borrower")
    )
    _emit(logs, on_message, "negotiation", "borrower", borrower_text)

    lender_ok = _effective_ratification(
        party="lender",
        package=package,
        terms=lender_terms,
        llm_decision=_parse_ratification_decision(lender_text),
        logs=logs,
        on_message=on_message,
    )
    borrower_ok = _effective_ratification(
        party="borrower",
        package=package,
        terms=borrower_terms,
        llm_decision=_parse_ratification_decision(borrower_text),
        logs=logs,
        on_message=on_message,
    )

    if lender_ok and borrower_ok:
        note = (
            "Both lender and borrower ratified the middleman package "
            "(inside each side's hard numeric walls)."
        )
        _emit(logs, on_message, "fairness", "fairness_agent", note)
        return True, note

    parts: list[str] = []
    if not lender_ok:
        parts.append("lender — outside hard walls")
    if not borrower_ok:
        parts.append("borrower — outside hard walls")
    note = "Middleman ratification failed — " + "; ".join(parts) + "."
    _emit(logs, on_message, "fairness", "fairness_agent", note)
    return False, note


def _silent_fairness_tweak_loop(
    *,
    final_deal: DealTerms,
    scores: Scores,
    borrower_terms: BorrowerTerms,
    lender_terms: LenderTerms,
    settings: Settings,
    logs: list[AgentRunLog],
    on_message: MessageHandler | None,
) -> tuple[DealTerms, Scores, list[str], list[str]]:
    """
    Old method: nudge the package inside overlapping ranges while narrowing score gap to ≤2.
    """
    fairness = check_fairness(scores)
    validation_issues = evaluate_deal_limits(
        final_deal, borrower_terms, lender_terms
    ).blocking_issues
    soft_pass_notes = evaluate_deal_limits(
        final_deal, borrower_terms, lender_terms
    ).soft_pass_notes
    if validation_issues:
        closed, close_notes = close_deal_via_fairness(
            final_deal,
            borrower_terms,
            lender_terms,
            scores=scores,
            reason=(
                "Deterministic fairness tweak: projecting into overlap and balancing scores."
            ),
        )
        if closed is not None:
            final_deal = closed
            _emit(
                logs,
                on_message,
                "fairness",
                "fairness_agent",
                "Fairness agent projected into both sides' ranges:\n"
                + "\n".join(f"- {n}" for n in close_notes)
                + f"\nTweaked deal:\n{format_deal(final_deal)}",
            )
            scores = score_deal(final_deal, borrower_terms, lender_terms)
            _emit(logs, on_message, "ranking", "borrower_ranker", scores.borrower_rationale)
            _emit(logs, on_message, "ranking", "lender_ranker", scores.lender_rationale)
            fairness = check_fairness(scores)
            limit_check = evaluate_deal_limits(final_deal, borrower_terms, lender_terms)
            validation_issues = limit_check.blocking_issues
            soft_pass_notes = limit_check.soft_pass_notes

    adjustment_attempt = 0
    while (
        not fairness.passed
        and not validation_issues
        and final_deal.consensus_reached
        and adjustment_attempt < max(settings.max_fairness_adjustments, 1)
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
        if deals_match(final_deal, previous_deal):
            break

        adjustment_attempt += 1
        _emit(
            logs,
            on_message,
            "fairness",
            "fairness_agent",
            f"{adjustment_note}\nAdjusted deal:\n{format_deal(final_deal)}",
        )

        limit_check = evaluate_deal_limits(final_deal, borrower_terms, lender_terms)
        if limit_check.blocking_issues:
            closed, close_notes = close_deal_via_fairness(
                previous_deal,
                borrower_terms,
                lender_terms,
                scores=previous_scores,
                reason=(
                    "Fairness nudge left hard limits — locking a balanced in-range package."
                ),
            )
            if closed is not None:
                final_deal = closed
                _emit(
                    logs,
                    on_message,
                    "fairness",
                    "fairness_agent",
                    "Fairness nudge left limits — locked viable package:\n"
                    + "\n".join(f"- {n}" for n in close_notes)
                    + f"\nTweaked deal:\n{format_deal(final_deal)}",
                )
                scores = score_deal(final_deal, borrower_terms, lender_terms)
                _emit(
                    logs, on_message, "ranking", "borrower_ranker", scores.borrower_rationale
                )
                _emit(logs, on_message, "ranking", "lender_ranker", scores.lender_rationale)
                fairness = check_fairness(scores)
                limit_check = evaluate_deal_limits(
                    final_deal, borrower_terms, lender_terms
                )
                validation_issues = limit_check.blocking_issues
                soft_pass_notes = limit_check.soft_pass_notes
            else:
                final_deal = previous_deal
                validation_issues = evaluate_deal_limits(
                    final_deal, borrower_terms, lender_terms
                ).blocking_issues
            break

        validation_issues = limit_check.blocking_issues
        soft_pass_notes = limit_check.soft_pass_notes
        scores = score_deal(final_deal, borrower_terms, lender_terms)
        _emit(logs, on_message, "ranking", "borrower_ranker", scores.borrower_rationale)
        _emit(logs, on_message, "ranking", "lender_ranker", scores.lender_rationale)
        fairness = check_fairness(scores)
        if fairness.fairness_gap >= previous_gap:
            final_deal = previous_deal
            scores = previous_scores
            fairness = check_fairness(previous_scores)
            _emit(
                logs,
                on_message,
                "fairness",
                "fairness_agent",
                "Fairness adjustment did not narrow the score gap — keeping prior deal.",
            )
            break

    # Final backstop: still unfair or out of range → force close+balance.
    limit_check = evaluate_deal_limits(final_deal, borrower_terms, lender_terms)
    validation_issues = limit_check.blocking_issues
    soft_pass_notes = limit_check.soft_pass_notes
    fairness = check_fairness(scores)
    if validation_issues or not fairness.passed:
        closed, close_notes = close_deal_via_fairness(
            final_deal,
            borrower_terms,
            lender_terms,
            scores=scores,
            reason=(
                "Silent fairness tweaks still short of a fair in-range deal — "
                "fairness agent applying final score balance within both sides' ranges."
            ),
        )
        if closed is not None:
            final_deal = closed
            _emit(
                logs,
                on_message,
                "fairness",
                "fairness_agent",
                "Final fairness balance within both sides' ranges:\n"
                + "\n".join(f"- {n}" for n in close_notes)
                + f"\nFinal deal:\n{format_deal(final_deal)}",
            )
            scores = score_deal(final_deal, borrower_terms, lender_terms)
            _emit(logs, on_message, "ranking", "borrower_ranker", scores.borrower_rationale)
            _emit(logs, on_message, "ranking", "lender_ranker", scores.lender_rationale)
            # Extra nudge loop if close still unfair (rare).
            fairness = check_fairness(scores)
            for _ in range(settings.max_fairness_adjustments):
                if fairness.passed:
                    break
                nudged = adjust_deal_for_fairness(
                    final_deal, scores, borrower_terms, lender_terms
                )
                if deals_match(nudged, final_deal):
                    break
                if evaluate_deal_limits(nudged, borrower_terms, lender_terms).blocking_issues:
                    break
                final_deal = nudged.model_copy(update={"consensus_reached": True})
                scores = score_deal(final_deal, borrower_terms, lender_terms)
                fairness = check_fairness(scores)
                _emit(
                    logs,
                    on_message,
                    "fairness",
                    "fairness_agent",
                    f"Extra fairness nudge to bring gap ≤ 2.\nAdjusted deal:\n{format_deal(final_deal)}",
                )
            limit_check = evaluate_deal_limits(final_deal, borrower_terms, lender_terms)
            validation_issues = limit_check.blocking_issues
            soft_pass_notes = limit_check.soft_pass_notes

    return final_deal, scores, validation_issues, soft_pass_notes


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
    contract_text: str | None = None,
    llm_model: str | None = None,
    *,
    persona_id: str | None = None,
    persona_name: str | None = None,
    attempt: int | None = None,
    save_interaction: bool = True,
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

    def _finish(result: WorkflowResult) -> WorkflowRun:
        if save_interaction:
            try:
                append_interaction(
                    result,
                    model_id=settings.model,
                    persona_id=persona_id,
                    persona_name=persona_name,
                    attempt=attempt,
                )
            except Exception:  # noqa: BLE001 — never fail the workflow on logging
                import logging

                logging.getLogger(__name__).exception(
                    "Failed to save results/interactions.json"
                )
        return WorkflowRun(result=result, logs=logs)

    try:
        _emit(
            logs,
            on_message,
            "intake",
            "system",
            f"Using model: {settings.model}",
        )

        if not intake_complete(borrower_terms, lender_terms):
            intake_agent = create_assistant_agent(
                "intake_agent",
                INTAKE_AGENT_PROMPT,
                description="Gathers missing borrower and lender information before negotiation.",
                model_client=model_client,
            )
            missing = {
                "borrower": borrower_missing_fields(borrower_terms),
                "lender": lender_missing_fields(lender_terms),
            }
            intake_response = await ask_agent(
                intake_agent,
                "Review these partial submissions and list what is still missing.\n"
                f"Borrower terms: {borrower_terms.model_dump_json()}\n"
                f"Lender terms: {lender_terms.model_dump_json()}\n"
                f"Missing: {missing}",
            )
            _emit(logs, on_message, "intake", "intake_agent", intake_response)

        feasibility = check_feasibility(borrower_terms, lender_terms)
        if feasibility.status == FeasibilityStatus.IMPOSSIBLE:
            for reason in feasibility.reasons:
                _emit(logs, on_message, "feasibility", "system", reason)
            return _finish(
                WorkflowResult(
                    status=WorkflowStatus.IMPOSSIBLE,
                    reasons=feasibility.reasons,
                    llm_metrics=metrics.snapshot(model_client),
                )
            )

        _emit(logs, on_message, "feasibility", "system", "Deal is feasible. Starting negotiation.")

        if opening_offer is None and contract_text and contract_text.strip():
            _emit(
                logs,
                on_message,
                "intake",
                "system",
                "Reading lender contract with local Llama 3.2…",
            )
            try:
                opening_offer = await extract_opening_offer_with_local_llama(
                    contract_text,
                    settings=settings,
                )
            except OpeningOfferExtractionError as exc:
                _emit(logs, on_message, "intake", "system", str(exc))
                return _finish(
                    WorkflowResult(
                        status=WorkflowStatus.NO_DEAL,
                        reasons=[str(exc)],
                        llm_metrics=metrics.snapshot(model_client),
                    )
                )

        seeded = opening_offer is not None
        if seeded and opening_offer is not None:
            opening_offer = opening_offer.model_copy(update={"consensus_reached": False})
            announcement = format_opening_offer_announcement(opening_offer)
            _emit(logs, on_message, "negotiation", "lender_negotiator", announcement)
            task = _seeded_negotiation_task(opening_offer)
            seed_transcript = transcript_line("lender_negotiator", announcement)
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
        negotiation_text, rounds = await _run_negotiation_team(
            team,
            task,
            logs,
            on_message,
            terms_by_source=_negotiator_terms_by_source(borrower_terms, lender_terms),
        )
        if seed_transcript:
            negotiation_text = f"{seed_transcript}\n\n{negotiation_text}".strip()

        final_deal = extract_final_deal(negotiation_text, borrower_terms, lender_terms)
        validation_issues: list[str] = []
        soft_pass_notes: list[str] = []
        if final_deal is not None:
            _emit(
                logs,
                on_message,
                "negotiation",
                "system",
                f"Parsed deal:\n{format_deal(final_deal)}",
            )
            limit_check = evaluate_deal_limits(
                final_deal, borrower_terms, lender_terms
            )
            validation_issues = limit_check.blocking_issues
            soft_pass_notes = limit_check.soft_pass_notes
            for note in soft_pass_notes:
                _emit(logs, on_message, "negotiation", "system", f"Soft bend: {note}")
            for issue in validation_issues:
                _emit(logs, on_message, "negotiation", "system", f"Deal validation: {issue}")

            # Hard breaches only: tiny touch-up, else middleman irons later.
            # Soft bends do not trigger recovery — reviewer weighs them in context.
            if (
                validation_issues
                and final_deal is not None
                and final_deal.consensus_reached
            ):
                repaired, repair_notes = repair_clears_limit_issues(
                    final_deal, borrower_terms, lender_terms
                )
                if repaired is not None:
                    final_deal = repaired.model_copy(update={"consensus_reached": True})
                    _emit(
                        logs,
                        on_message,
                        "negotiation",
                        "system",
                        "Small validation touch-up into overlapping limits:\n"
                        + (
                            "\n".join(f"- {n}" for n in repair_notes)
                            if repair_notes
                            else "- no numeric moves needed"
                        )
                        + f"\nRepaired deal:\n{format_deal(final_deal)}",
                    )
                    limit_check = evaluate_deal_limits(
                        final_deal, borrower_terms, lender_terms
                    )
                    validation_issues = limit_check.blocking_issues
                    soft_pass_notes = limit_check.soft_pass_notes

            if (
                final_deal is not None
                and not validation_issues
                and final_deal.consensus_reached
            ):
                _emit(
                    logs,
                    on_message,
                    "negotiation",
                    "system",
                    "Deal passed range validation"
                    + (
                        " (including subtle soft bends — reviewer will weigh context)."
                        if soft_pass_notes
                        else "."
                    ),
                )

        # Snapshot the post-negotiation package before middleman ironing.
        negotiated_deal: DealTerms | None = final_deal

        # Middleman irons issues: lock + score-balance inside both sides' ranges.
        middleman_intervened = False
        had_invalid_consensus = bool(
            final_deal is not None
            and final_deal.consensus_reached
            and validation_issues
        )
        needs_mediator_close = (
            final_deal is None
            or not final_deal.consensus_reached
            or had_invalid_consensus
        )

        if needs_mediator_close:
            seed_scores = None
            if final_deal is not None:
                seed_scores = score_deal(final_deal, borrower_terms, lender_terms)
            close_reason = (
                "Consensus still outside hard limits — "
                "middleman locking a viable in-range deal, then balancing scores."
                if had_invalid_consensus
                else "No mutual accept after negotiation — "
                "middleman locking a viable deal, then balancing scores."
            )
            closed, close_notes = close_deal_via_fairness(
                final_deal,
                borrower_terms,
                lender_terms,
                scores=seed_scores,
                reason=close_reason,
            )
            note_block = "\n".join(f"- {n}" for n in close_notes)
            if closed is not None:
                final_deal = closed
                middleman_intervened = True
                limit_check = evaluate_deal_limits(
                    final_deal, borrower_terms, lender_terms
                )
                validation_issues = limit_check.blocking_issues
                soft_pass_notes = limit_check.soft_pass_notes
                _emit(
                    logs,
                    on_message,
                    "fairness",
                    "fairness_agent",
                    "Middleman locked a viable package:\n"
                    f"{note_block}\nClosed deal:\n{format_deal(final_deal)}",
                )
            else:
                _emit(
                    logs,
                    on_message,
                    "fairness",
                    "fairness_agent",
                    "Middleman could not produce a feasible package:\n" + note_block,
                )

        scores: Scores | None = None
        fairness = check_fairness(Scores(borrower_score=5, lender_score=5))
        middleman_ratify_note: str | None = None

        if final_deal is not None:
            scores = _rank_deal(
                final_deal,
                borrower_terms,
                lender_terms,
                logs,
                on_message,
            )
            fairness = check_fairness(scores)

            # Unfair / still invalid: silent score tweaks within both sides' ranges.
            if final_deal.consensus_reached and (
                not fairness.passed
                or evaluate_deal_limits(
                    final_deal, borrower_terms, lender_terms
                ).blocking_issues
            ):
                pre_tweak = final_deal.model_copy()
                (
                    final_deal,
                    scores,
                    validation_issues,
                    soft_pass_notes,
                ) = _silent_fairness_tweak_loop(
                    final_deal=final_deal,
                    scores=scores,
                    borrower_terms=borrower_terms,
                    lender_terms=lender_terms,
                    settings=settings,
                    logs=logs,
                    on_message=on_message,
                )
                fairness = check_fairness(scores)
                if not deals_match(final_deal, pre_tweak):
                    middleman_intervened = True
            else:
                limit_check = evaluate_deal_limits(
                    final_deal, borrower_terms, lender_terms
                )
                validation_issues = limit_check.blocking_issues
                soft_pass_notes = limit_check.soft_pass_notes

            # Present ironed package once to each side — accept/reject only.
            if (
                middleman_intervened
                and final_deal.consensus_reached
                and not validation_issues
                and fairness.passed
            ):
                ratified, middleman_ratify_note = await _ratify_middleman_package(
                    package=final_deal,
                    borrower_terms=borrower_terms,
                    lender_terms=lender_terms,
                    model_client=model_client,
                    settings=settings,
                    logs=logs,
                    on_message=on_message,
                )
                final_deal = final_deal.model_copy(
                    update={"consensus_reached": bool(ratified)}
                )
        else:
            soft_pass_notes = []
            _emit(
                logs,
                on_message,
                "ranking",
                "system",
                "Skipping ranking — no confirmed deal to score.",
            )

        reviewer = create_assistant_agent(
            "reviewer_agent",
            REVIEWER_AGENT_PROMPT,
            description="Validates the deal against original terms and required loan details.",
            model_client=model_client,
        )
        deal_section = (
            f"Agreed deal (JSON):\n{format_deal(final_deal)}\n\n"
            if final_deal is not None
            else f"Negotiation transcript:\n{negotiation_text}\n\n"
        )

        validation_section = (
            "Hard (blocking) validation issues:\n"
            + (
                "\n".join(f"- {issue}" for issue in validation_issues)
                if validation_issues
                else "- none"
            )
            + "\n\nSubtle soft-bend notes (advisory — judge in overall deal context, "
            "not as automatic failures):\n"
            + (
                "\n".join(f"- {note}" for note in soft_pass_notes)
                if soft_pass_notes
                else "- none"
            )
            + "\n\nOriginal preference context (for feasibility vs initial ask):\n"
            f"- Borrower deposit {borrower_terms.min_downpayment:g}–{borrower_terms.max_downpayment:g}, "
            f"rate {borrower_terms.min_interest_rate_pct:g}–{borrower_terms.max_interest_rate_pct:g}%, "
            f"fee {borrower_terms.min_arrangement_fee:g}–{borrower_terms.max_arrangement_fee:g}, "
            f"cashback {borrower_terms.min_cashback:g}–{borrower_terms.max_cashback:g}\n"
            f"- Lender deposit {lender_terms.min_downpayment:g}–{lender_terms.max_downpayment:g}, "
            f"rate {lender_terms.min_interest_rate_pct:g}–{lender_terms.max_interest_rate_pct:g}%, "
            f"fee {lender_terms.min_arrangement_fee:g}–{lender_terms.max_arrangement_fee:g}, "
            f"cashback {lender_terms.min_cashback:g}–{lender_terms.max_cashback:g}\n\n"
        )

        review_prompt = (
            f"{deal_section}"
            f"{validation_section}"
            + (
                f"Borrower score: {scores.borrower_score:.1f}/10\n"
                f"Lender score: {scores.lender_score:.1f}/10\n"
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
        reasons.extend(soft_pass_notes)
        if final_deal is None:
            reasons.append("No structured deal could be parsed from the negotiation.")
        elif not final_deal.consensus_reached:
            if middleman_ratify_note and "ratification failed" in middleman_ratify_note.lower():
                reasons.append(middleman_ratify_note)
            else:
                reasons.append("Negotiation ended without mutual consensus.")
        elif middleman_ratify_note:
            reasons.append(middleman_ratify_note)
        if not fairness.passed and fairness.feedback:
            reasons.append(fairness.feedback)

        return _finish(
            WorkflowResult(
                status=status,
                deal=final_deal,
                negotiated_deal=negotiated_deal,
                scores=scores,
                review=review,
                reasons=reasons,
                rounds=rounds,
                llm_metrics=metrics.snapshot(model_client),
            )
        )
    finally:
        await model_client.close()
