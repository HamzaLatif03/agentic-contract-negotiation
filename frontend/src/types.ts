export interface BorrowerTerms {
  min_downpayment: number;
  max_downpayment: number;
  min_interest_rate_pct: number;
  max_interest_rate_pct: number;
  min_loan_length_years: number;
  max_loan_length_years: number;
  fixed_preference: number;
  variable_preference: number;
}

export interface LenderTerms {
  min_downpayment: number;
  max_downpayment: number;
  min_interest_rate_pct: number;
  max_interest_rate_pct: number;
  min_loan_length_years: number;
  max_loan_length_years: number;
  fixed_preference: number;
  variable_preference: number;
}

export interface NegotiateRequest {
  borrower: BorrowerTerms;
  lender: LenderTerms;
  opening_offer?: DealTerms | null;
  llm_model?: string | null;
}

export interface DealTerms {
  downpayment: number;
  interest_rate_pct: number;
  loan_length_years: number;
  interest_structure: number;
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
  deal?: DealTerms;
  negotiated_deal?: DealTerms;
  fairness_adjusted?: boolean;
  scores?: Scores;
  review?: ReviewFeedback;
  reasons: string[];
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

export function structureKind(value: number): "fixed" | "variable" {
  return value <= 5 ? "fixed" : "variable";
}

export function structureLabel(value: number): string {
  if (value <= 2) return "mostly fixed";
  if (value >= 9) return "mostly variable";
  if (value <= 4) return "leaning fixed";
  if (value >= 7) return "leaning variable";
  return "balanced";
}
