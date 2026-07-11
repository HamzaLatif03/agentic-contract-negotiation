import type { DealTerms, WorkflowResult } from "../types";
import { structureKind } from "../types";
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

function ScoreBar({ label, score, color }: { label: string; score: number; color: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-600">
        <span>{label}</span>
        <span className="font-semibold">{score}/10</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${score * 10}%` }}
        />
      </div>
    </div>
  );
}

function formatDealLine(deal: DealTerms): string {
  return `£${deal.downpayment.toLocaleString()} down · ${deal.interest_rate_pct}% · ${deal.loan_length_years}yr · ${structureKind(deal.interest_structure)}`;
}

function DealGrid({ deal }: { deal: DealTerms }) {
  return (
    <div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-4 text-sm">
      <div>
        <p className="text-xs text-slate-500">Downpayment</p>
        <p className="font-semibold text-slate-900">£{deal.downpayment.toLocaleString()}</p>
      </div>
      <div>
        <p className="text-xs text-slate-500">Interest rate</p>
        <p className="font-semibold text-slate-900">{deal.interest_rate_pct}%</p>
      </div>
      <div>
        <p className="text-xs text-slate-500">Loan length</p>
        <p className="font-semibold text-slate-900">{deal.loan_length_years} years</p>
      </div>
      <div>
        <p className="text-xs text-slate-500">Interest structure</p>
        <p className="font-semibold capitalize text-slate-900">
          {structureKind(deal.interest_structure)}
        </p>
      </div>
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
      <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-5">
        <h2 className="text-sm font-semibold text-slate-600">Result</h2>
        <p className="mt-2 text-sm text-slate-400">
          Final deal, scores, and approval status will appear here.
        </p>
      </div>
    );
  }

  const gap =
    result.scores != null
      ? Math.abs(result.scores.borrower_score - result.scores.lender_score)
      : null;

  const showNegotiatedComparison =
    result.negotiated_deal != null &&
    result.deal != null &&
    !dealsEqual(result.negotiated_deal, result.deal);

  const reasonTone =
    result.status === "approved"
      ? "text-slate-600"
      : result.status === "impossible" || result.status === "rejected"
        ? "text-orange-800"
        : "text-amber-800";

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-800">Outcome</h2>
        <StatusBadge status={result.status} />
      </div>

      {result.deal && (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {result.fairness_adjusted ? "Final terms (after fairness)" : "Agreed terms"}
          </p>
          <DealGrid deal={result.deal} />
        </div>
      )}

      {showNegotiatedComparison && result.negotiated_deal && (
        <div className="rounded-lg border border-slate-100 bg-white px-3 py-2 text-xs text-slate-500">
          <p className="font-medium text-slate-600">Originally negotiated</p>
          <p className="mt-1">{formatDealLine(result.negotiated_deal)}</p>
        </div>
      )}

      {result.scores && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Scores
            </p>
            {gap != null && (
              <p className="text-xs text-slate-500">
                Gap {gap}/2
              </p>
            )}
          </div>
          <ScoreBar
            label="Borrower"
            score={result.scores.borrower_score}
            color="bg-blue-500"
          />
          <ScoreBar
            label="Lender"
            score={result.scores.lender_score}
            color="bg-violet-500"
          />
        </div>
      )}

      {result.llm_metrics && (
        <div className="space-y-2 border-t border-slate-100 pt-3">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            LLM run metrics
          </p>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs text-slate-600">
            <div>
              <dt className="text-slate-400">Model</dt>
              <dd className="font-medium text-slate-800">{result.llm_metrics.model}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Total tokens</dt>
              <dd className="font-medium text-slate-800">
                {result.llm_metrics.total_tokens.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Prompt tokens</dt>
              <dd className="font-medium text-slate-800">
                {result.llm_metrics.prompt_tokens.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Completion tokens</dt>
              <dd className="font-medium text-slate-800">
                {result.llm_metrics.completion_tokens.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Time to first output</dt>
              <dd className="font-medium text-slate-800">
                {result.llm_metrics.time_to_first_token_ms != null
                  ? formatDuration(result.llm_metrics.time_to_first_token_ms)
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Total duration</dt>
              <dd className="font-medium text-slate-800">
                {formatDuration(result.llm_metrics.duration_ms)}
              </dd>
            </div>
          </dl>
        </div>
      )}

      {result.reasons.length > 0 && (
        <ul className={`space-y-1 border-t border-slate-100 pt-3 text-xs ${reasonTone}`}>
          {result.reasons.map((reason) => (
            <li key={reason}>• {reason}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
