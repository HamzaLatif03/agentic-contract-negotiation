import type { DealTerms, RateType, RepaymentType, Scores, WorkflowResult } from "./types";

function asRateType(value: unknown): RateType {
  const text = String(value ?? "fixed").toLowerCase();
  if (text === "tracker" || text === "discount" || text === "fixed") return text;
  const n = Number(value);
  if (Number.isFinite(n)) {
    if (n <= 4) return "fixed";
    if (n <= 7) return "discount";
    return "tracker";
  }
  return "fixed";
}

function asRepayment(value: unknown): RepaymentType {
  const text = String(value ?? "capital_repayment").toLowerCase().replaceAll("-", "_");
  return text === "interest_only" ? "interest_only" : "capital_repayment";
}

export function parseDealJson(raw: string): DealTerms | null {
  try {
    const data = JSON.parse(raw) as Partial<DealTerms> & {
      interest_structure?: number;
      deposit?: number;
    };
    const downpayment = data.downpayment ?? data.deposit;
    if (
      typeof downpayment !== "number" ||
      typeof data.interest_rate_pct !== "number" ||
      typeof data.loan_length_years !== "number"
    ) {
      return null;
    }
    const rateType =
      data.rate_type != null ? asRateType(data.rate_type) : asRateType(data.interest_structure);
    return {
      downpayment,
      interest_rate_pct: data.interest_rate_pct,
      loan_length_years: data.loan_length_years,
      rate_type: rateType,
      initial_period_years: Number(data.initial_period_years ?? 5),
      arrangement_fee: Number(data.arrangement_fee ?? 0),
      cashback: Number(data.cashback ?? 0),
      overpayment_allowance_pct: Number(data.overpayment_allowance_pct ?? 10),
      erc_pct: Number(data.erc_pct ?? 0),
      repayment_type: asRepayment(data.repayment_type),
      portable: Boolean(data.portable ?? true),
      free_valuation: Boolean(data.free_valuation ?? false),
      free_legal: Boolean(data.free_legal ?? false),
      consensus_reached: Boolean(data.consensus_reached),
    };
  } catch {
    return null;
  }
}

export function extractDealFromOutput(output: string): {
  deal: DealTerms;
  source: "negotiated" | "adjusted";
} | null {
  const negotiated = output.match(/Parsed deal:\s*\n(\{[\s\S]*?\})/);
  if (negotiated) {
    const deal = parseDealJson(negotiated[1]);
    if (deal) return { deal, source: "negotiated" };
  }

  const adjusted = output.match(/Adjusted deal:\s*\n(\{[\s\S]*?\})/);
  if (adjusted) {
    const deal = parseDealJson(adjusted[1]);
    if (deal) return { deal, source: "adjusted" };
  }

  return null;
}

export function extractScoreFromRanking(output: string): number | null {
  const match = output.match(/Score:\s*(\d+(?:\.\d+)?)\s*\/\s*10/i);
  if (!match) return null;
  const score = Number(match[1]);
  if (!Number.isFinite(score)) return null;
  return Math.max(1, Math.min(10, Math.round(score * 10) / 10));
}

export function dealsEqual(a: DealTerms, b: DealTerms): boolean {
  return (
    a.downpayment === b.downpayment &&
    a.interest_rate_pct === b.interest_rate_pct &&
    a.loan_length_years === b.loan_length_years &&
    a.rate_type === b.rate_type &&
    a.initial_period_years === b.initial_period_years &&
    a.arrangement_fee === b.arrangement_fee &&
    a.cashback === b.cashback &&
    a.overpayment_allowance_pct === b.overpayment_allowance_pct &&
    a.erc_pct === b.erc_pct &&
    a.repayment_type === b.repayment_type &&
    a.portable === b.portable &&
    a.free_valuation === b.free_valuation &&
    a.free_legal === b.free_legal
  );
}

export function mergeProgressResult(
  prev: WorkflowResult | null,
  patch: Partial<WorkflowResult>,
): WorkflowResult {
  return {
    status: patch.status ?? prev?.status ?? "in_progress",
    deal_status: patch.deal_status ?? prev?.deal_status ?? patch.status ?? prev?.status,
    deal: patch.deal ?? prev?.deal,
    negotiated_deal: patch.negotiated_deal ?? prev?.negotiated_deal,
    fairness_adjusted: patch.fairness_adjusted ?? prev?.fairness_adjusted,
    scores: patch.scores ?? prev?.scores,
    review: patch.review ?? prev?.review,
    reasons: patch.reasons ?? prev?.reasons ?? [],
    rounds: patch.rounds ?? prev?.rounds,
    llm_metrics: patch.llm_metrics ?? prev?.llm_metrics,
  };
}

export function applyFeedEventToResult(
  prev: WorkflowResult | null,
  stage: string,
  agent: string,
  output: string,
): WorkflowResult | null {
  const extracted = extractDealFromOutput(output);
  if (extracted) {
    const patch: Partial<WorkflowResult> = {
      status: "in_progress",
      deal: extracted.deal,
    };
    if (extracted.source === "negotiated") {
      patch.negotiated_deal = extracted.deal;
      patch.fairness_adjusted = false;
    } else {
      patch.fairness_adjusted = true;
    }
    return mergeProgressResult(prev, patch);
  }

  if (stage === "ranking" && (agent === "borrower_ranker" || agent === "lender_ranker")) {
    const score = extractScoreFromRanking(output);
    if (score == null) return prev;

    const prevScores: Scores = prev?.scores ?? {
      borrower_score: 5,
      lender_score: 5,
      borrower_rationale: "",
      lender_rationale: "",
    };

    const scores: Scores =
      agent === "borrower_ranker"
        ? {
            ...prevScores,
            borrower_score: score,
            borrower_rationale: output,
          }
        : {
            ...prevScores,
            lender_score: score,
            lender_rationale: output,
          };

    return mergeProgressResult(prev, { status: "in_progress", scores });
  }

  return prev;
}
