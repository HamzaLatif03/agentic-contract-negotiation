import type { DealTerms } from "../types";
import { formatDealLine } from "../types";

interface ContractUploadProps {
  sourceFilename: string | null;
  disabled: boolean;
  error: string | null;
  previewLoading: boolean;
  previewDeal: DealTerms | null;
  previewAnnouncement: string | null;
  onUpload: (file: File) => void;
  onClear: () => void;
}

function PreviewGrid({ deal }: { deal: DealTerms }) {
  const cells: { label: string; value: string }[] = [
    { label: "Deposit", value: `£${Number(deal.downpayment).toLocaleString("en-GB")}` },
    { label: "Rate", value: `${deal.interest_rate_pct}% ${deal.rate_type}` },
    { label: "Initial period", value: `${deal.initial_period_years} years` },
    { label: "Full term", value: `${deal.loan_length_years} years` },
    { label: "Repayment", value: String(deal.repayment_type).replaceAll("_", " ") },
    {
      label: "Arrangement fee",
      value: `£${Number(deal.arrangement_fee).toLocaleString("en-GB")}`,
    },
    { label: "Cashback", value: `£${Number(deal.cashback).toLocaleString("en-GB")}` },
    { label: "Overpayment", value: `${deal.overpayment_allowance_pct}%` },
    { label: "ERC", value: `${deal.erc_pct}%` },
    { label: "Portable", value: deal.portable ? "Yes" : "No" },
    { label: "Free valuation", value: deal.free_valuation ? "Yes" : "No" },
    { label: "Free legal", value: deal.free_legal ? "Yes" : "No" },
  ];
  return (
    <div className="mt-3 grid grid-cols-2 gap-3 rounded-lg bg-white/80 p-3 text-sm sm:grid-cols-3">
      {cells.map((cell) => (
        <div key={cell.label}>
          <p className="text-xs text-slate-500">{cell.label}</p>
          <p className="font-semibold capitalize text-slate-900">{cell.value}</p>
        </div>
      ))}
    </div>
  );
}

export default function ContractUpload({
  sourceFilename,
  disabled,
  error,
  previewLoading,
  previewDeal,
  previewAnnouncement,
  onUpload,
  onClear,
}: ContractUploadProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Lender opening contract (PDF)</h2>
          <p className="mt-1 text-sm text-slate-500">
            Optional. Local Llama 3.2 reads the PDF on upload and shows the opening offer before
            negotiation starts.
          </p>
        </div>
        <div className="flex gap-2">
          <label
            className={`cursor-pointer rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 ${
              disabled || previewLoading ? "pointer-events-none opacity-50" : ""
            }`}
          >
            {previewLoading ? "Reading PDF…" : "Upload PDF"}
            <input
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              disabled={disabled || previewLoading}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) onUpload(file);
                event.target.value = "";
              }}
            />
          </label>
          {sourceFilename && (
            <button
              type="button"
              onClick={onClear}
              disabled={disabled || previewLoading}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {error && (
        <p className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {previewLoading && (
        <p className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          Local Llama 3.2 is extracting the opening offer…
        </p>
      )}

      {!previewLoading && sourceFilename ? (
        <div className="rounded-lg border border-teal-100 bg-teal-50/60 px-4 py-3 text-sm text-teal-900">
          <p>
            Attached: <span className="font-medium">{sourceFilename}</span>
          </p>
          {previewAnnouncement ? (
            <p className="mt-2 text-sm text-teal-800">{previewAnnouncement.split("\n")[0]}</p>
          ) : null}
          {previewDeal ? (
            <>
              <p className="mt-2 text-xs font-medium uppercase tracking-wide text-teal-700/80">
                Previewed opening terms
              </p>
              <p className="mt-1 text-xs text-teal-800/80">{formatDealLine(previewDeal)}</p>
              <PreviewGrid deal={previewDeal} />
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
