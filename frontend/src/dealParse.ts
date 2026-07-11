import type { DealTerms, Scores, WorkflowResult } from "./types";

export function parseDealJson(raw: string): DealTerms | null {
  try {
    const data = JSON.parse(raw) as Partial<DealTerms>;
    if (
      typeof data.downpayment !== "number" ||
      typeof data.interest_rate_pct !== "number" ||
      typeof data.loan_length_years !== "number" ||
      typeof data.interest_structure !== "number"
    ) {
      return null;
    }
    return {
      downpayment: data.downpayment,
      interest_rate_pct: data.interest_rate_pct,
      loan_length_years: data.loan_length_years,
      interest_structure: data.interest_structure,
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
  const match = output.match(/Score:\s*(\d+)\s*\/\s*10/i);
  return match ? Number(match[1]) : null;
}

export function dealsEqual(a: DealTerms, b: DealTerms): boolean {
  return (
    a.downpayment === b.downpayment &&
    a.interest_rate_pct === b.interest_rate_pct &&
    a.loan_length_years === b.loan_length_years &&
    a.interest_structure === b.interest_structure
  );
}

export function mergeProgressResult(
  prev: WorkflowResult | null,
  patch: Partial<WorkflowResult>,
): WorkflowResult {
  return {
    status: patch.status ?? prev?.status ?? "in_progress",
    deal: patch.deal ?? prev?.deal,
    negotiated_deal: patch.negotiated_deal ?? prev?.negotiated_deal,
    fairness_adjusted: patch.fairness_adjusted ?? prev?.fairness_adjusted,
    scores: patch.scores ?? prev?.scores,
    review: patch.review ?? prev?.review,
    reasons: patch.reasons ?? prev?.reasons ?? [],
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
