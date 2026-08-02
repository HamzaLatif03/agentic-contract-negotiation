export type RateType = "fixed" | "tracker" | "discount";
export type RepaymentType = "capital_repayment" | "interest_only";
export type InitialPeriodYears = 2 | 5 | 10;

/** 1 = strongly prefer OFF, 5 = flexible, 10 = strongly prefer ON */
export type FeaturePreference = number;

export interface PartyTerms {
  min_downpayment: number;
  max_downpayment: number;
  min_interest_rate_pct: number;
  max_interest_rate_pct: number;
  min_loan_length_years: number;
  max_loan_length_years: number;
  min_arrangement_fee: number;
  max_arrangement_fee: number;
  min_cashback: number;
  max_cashback: number;
  min_overpayment_allowance_pct: number;
  max_overpayment_allowance_pct: number;
  min_erc_pct: number;
  max_erc_pct: number;
  preferred_rate_type: RateType;
  preferred_initial_period_years: InitialPeriodYears;
  preferred_repayment_type: RepaymentType;
  portable_preference: FeaturePreference;
  free_valuation_preference: FeaturePreference;
  free_legal_preference: FeaturePreference;
}

export type BorrowerTerms = PartyTerms;
export type LenderTerms = PartyTerms;

export interface PersonaSummary {
  id: string;
  name: string;
  description: string;
  tag: string;
}

export interface PersonaTerms {
  id: string;
  name: string;
  description: string;
  tag: string;
  borrower: PartyTerms;
  lender: PartyTerms;
}

export interface NegotiateRequest {
  borrower: PartyTerms;
  lender: PartyTerms;
  llm_model?: string | null;
  contract_text?: string | null;
  persona_id?: string | null;
  persona_name?: string | null;
  attempt?: number | null;
}

export interface DealTerms {
  downpayment: number;
  interest_rate_pct: number;
  loan_length_years: number;
  rate_type: RateType;
  initial_period_years: InitialPeriodYears | number;
  arrangement_fee: number;
  cashback: number;
  overpayment_allowance_pct: number;
  erc_pct: number;
  repayment_type: RepaymentType;
  portable: boolean;
  free_valuation: boolean;
  free_legal: boolean;
  consensus_reached: boolean;
}

export interface Scores {
  borrower_score: number;
  lender_score: number;
  borrower_rationale: string;
  lender_rationale: string;
}

export interface ReviewFeedback {
  approved: boolean;
  issues: string[];
}

export interface LlmRunMetrics {
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  time_to_first_token_ms: number | null;
  duration_ms: number;
}

export interface WorkflowResult {
  status: "in_progress" | "impossible" | "approved" | "rejected" | "no_deal";
  deal_status?: "in_progress" | "impossible" | "approved" | "rejected" | "no_deal";
  deal?: DealTerms;
  negotiated_deal?: DealTerms;
  fairness_adjusted?: boolean;
  scores?: Scores;
  review?: ReviewFeedback;
  reasons: string[];
  rounds?: number | null;
  llm_metrics?: LlmRunMetrics;
}

export interface FeedEvent {
  id: string;
  stage: string;
  agent: string;
  output: string;
  timestamp: number;
}

export interface StreamMessage {
  type: "event" | "complete" | "error";
  stage?: string;
  agent?: string;
  output?: string;
  result?: WorkflowResult;
  message?: string;
}

export function formatDealLine(deal: DealTerms): string {
  const bits = [
    `£${deal.downpayment.toLocaleString("en-GB")} deposit`,
    `${deal.interest_rate_pct}% ${deal.rate_type} (${deal.initial_period_years}yr)`,
    `${deal.loan_length_years}yr term`,
    deal.repayment_type.replaceAll("_", " "),
  ];
  if (deal.arrangement_fee) bits.push(`fee £${deal.arrangement_fee.toLocaleString("en-GB")}`);
  if (deal.cashback) bits.push(`cashback £${deal.cashback.toLocaleString("en-GB")}`);
  bits.push(`overpay ${deal.overpayment_allowance_pct}%`);
  if (deal.erc_pct) bits.push(`ERC ${deal.erc_pct}%`);
  if (deal.portable) bits.push("portable");
  if (deal.free_valuation) bits.push("free val");
  if (deal.free_legal) bits.push("free legal");
  return bits.join(" · ");
}
