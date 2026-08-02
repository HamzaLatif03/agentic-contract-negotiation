import type { DealTerms, LlmRunMetrics, WorkflowResult } from "../types";
import { formatDealLine } from "../types";
import { dealsEqual } from "../dealParse";

interface ResultPanelProps {
  result: WorkflowResult | null;
  error: string | null;
}

function StatusBadge({ status }: { status: WorkflowResult["status"] }) {
  const styles = {
    approved: "bg-emerald-100 text-emerald-800",
    in_progress: "bg-amber-100 text-amber-800",
    impossible: "bg-red-100 text-red-800",
    rejected: "bg-orange-100 text-orange-800",
    no_deal: "bg-slate-200 text-slate-700",
  };

  const labels = {
    approved: "Approved",
    in_progress: "In progress",
    impossible: "Impossible",
    rejected: "Rejected",
    no_deal: "No deal",
  };

  return (
    <span
      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${styles[status]}`}
    >
      {labels[status]}
    </span>
  );
}

function formatScore(score: number): string {
  return (Math.round(score * 10) / 10).toFixed(1);
}

function ScoreBar({ label, score, color }: { label: string; score: number; color: string }) {
  const width = Math.max(0, Math.min(100, score * 10));
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-600">
        <span>{label}</span>
        <span className="font-semibold tabular-nums">{formatScore(score)}/10</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function DealGrid({ deal }: { deal: DealTerms }) {
  const cells: { label: string; value: string }[] = [
    { label: "Deposit", value: `£${deal.downpayment.toLocaleString("en-GB")}` },
    { label: "Rate", value: `${deal.interest_rate_pct}% ${deal.rate_type}` },
    { label: "Initial period", value: `${deal.initial_period_years} years` },
    { label: "Full term", value: `${deal.loan_length_years} years` },
    { label: "Repayment", value: deal.repayment_type.replaceAll("_", " ") },
    { label: "Arrangement fee", value: `£${deal.arrangement_fee.toLocaleString("en-GB")}` },
    { label: "Cashback", value: `£${deal.cashback.toLocaleString("en-GB")}` },
    { label: "Overpayment", value: `${deal.overpayment_allowance_pct}%` },
    { label: "ERC", value: `${deal.erc_pct}%` },
    { label: "Portable", value: deal.portable ? "Yes" : "No" },
    { label: "Free valuation", value: deal.free_valuation ? "Yes" : "No" },
    { label: "Free legal", value: deal.free_legal ? "Yes" : "No" },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-4 text-sm sm:grid-cols-3">
      {cells.map((cell) => (
        <div key={cell.label}>
          <p className="text-xs text-slate-500">{cell.label}</p>
          <p className="font-semibold capitalize text-slate-900">{cell.value}</p>
        </div>
      ))}
    </div>
  );
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const rem = seconds - minutes * 60;
  return `${minutes}m ${rem.toFixed(0)}s`;
}

function formatTokens(n: number): string {
  return n.toLocaleString("en-GB");
}

function tokensPerSecond(metrics: LlmRunMetrics): string | null {
  if (metrics.duration_ms <= 0 || metrics.completion_tokens <= 0) return null;
  const rate = metrics.completion_tokens / (metrics.duration_ms / 1000);
  return `${rate.toFixed(1)} tok/s`;
}

function MetricCell({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-slate-200/80 bg-white px-3 py-2.5">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums text-slate-900">{value}</p>
      {hint ? <p className="mt-0.5 text-[11px] text-slate-500">{hint}</p> : null}
    </div>
  );
}

function LlmMetricsCard({ metrics }: { metrics: LlmRunMetrics }) {
  const throughput = tokensPerSecond(metrics);
  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">LLM run</p>
        <p className="mt-1 text-sm font-semibold text-slate-900">{metrics.model}</p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <MetricCell
          label="Prompt tokens"
          value={formatTokens(metrics.prompt_tokens)}
          hint="Input to the model"
        />
        <MetricCell
          label="Completion tokens"
          value={formatTokens(metrics.completion_tokens)}
          hint="Model output"
        />
        <MetricCell
          label="Total tokens"
          value={formatTokens(metrics.total_tokens)}
          hint={throughput ? `≈ ${throughput} completion` : "Prompt + completion"}
        />
        <MetricCell
          label="Duration"
          value={formatDuration(metrics.duration_ms)}
          hint="Full workflow wall time"
        />
        <MetricCell
          label="Time to first output"
          value={
            metrics.time_to_first_token_ms != null
              ? formatDuration(metrics.time_to_first_token_ms)
              : "—"
          }
          hint="Until first agent message"
        />
        <MetricCell
          label="Prompt share"
          value={
            metrics.total_tokens > 0
              ? `${Math.round((metrics.prompt_tokens / metrics.total_tokens) * 100)}%`
              : "—"
          }
          hint="Of total tokens"
        />
      </div>
    </div>
  );
}

export default function ResultPanel({ result, error }: ResultPanelProps) {
  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-5">
        <h2 className="text-sm font-semibold text-red-800">Error</h2>
        <p className="mt-2 text-sm text-red-700">{error}</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="rounded-xl border border-dashed border-slate-200 bg-white p-5 text-sm text-slate-500">
        Outcome appears here after negotiation.
      </div>
    );
  }

  const gap =
    result.scores != null
      ? Math.round(
          Math.abs(result.scores.borrower_score - result.scores.lender_score) * 10,
        ) / 10
      : null;

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-800">Outcome</h2>
        <div className="flex items-center gap-2">
          {result.rounds != null ? (
            <span className="text-xs tabular-nums text-slate-500">
              {result.rounds} round{result.rounds === 1 ? "" : "s"}
            </span>
          ) : null}
          <StatusBadge status={result.status} />
        </div>
      </div>

      {result.deal && (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Agreed package</p>
          <DealGrid deal={result.deal} />
          {result.negotiated_deal &&
            result.fairness_adjusted &&
            !dealsEqual(result.deal, result.negotiated_deal) && (
              <p className="text-xs text-slate-500">
                Negotiated before fairness nudge: {formatDealLine(result.negotiated_deal)}
              </p>
            )}
        </div>
      )}

      {result.scores && (
        <div className="space-y-3">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Scores{gap != null ? ` · gap ${formatScore(gap)}` : ""}
          </p>
          <ScoreBar label="Borrower" score={result.scores.borrower_score} color="bg-blue-500" />
          <ScoreBar label="Lender" score={result.scores.lender_score} color="bg-violet-500" />
        </div>
      )}

      {result.reasons.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Notes</p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-slate-600">
            {result.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {result.llm_metrics && <LlmMetricsCard metrics={result.llm_metrics} />}
    </div>
  );
}
