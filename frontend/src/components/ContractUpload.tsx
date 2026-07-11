import type { DealTerms } from "../types";
import { structureLabel } from "../types";

interface ContractUploadProps {
  openingOffer: DealTerms | null;
  sourceFilename: string | null;
  disabled: boolean;
  busy: boolean;
  error: string | null;
  onUpload: (file: File) => void;
  onClear: () => void;
}

export default function ContractUpload({
  openingOffer,
  sourceFilename,
  disabled,
  busy,
  error,
  onUpload,
  onClear,
}: ContractUploadProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Lender opening contract (PDF)</h2>
          <p className="mt-1 text-sm text-slate-500">
            Upload a lender offer PDF. We extract the opening terms and the borrower counters from
            there.
          </p>
        </div>
        <div className="flex gap-2">
          <label
            className={`cursor-pointer rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 ${
              disabled || busy ? "pointer-events-none opacity-50" : ""
            }`}
          >
            {busy ? "Reading PDF…" : "Upload PDF"}
            <input
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              disabled={disabled || busy}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) onUpload(file);
                event.target.value = "";
              }}
            />
          </label>
          {openingOffer && (
            <button
              type="button"
              onClick={onClear}
              disabled={disabled || busy}
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

      {openingOffer ? (
        <div className="rounded-lg border border-teal-100 bg-teal-50/60 px-4 py-3 text-sm text-slate-700">
          <p className="font-medium text-teal-800">
            Opening offer ready{sourceFilename ? ` from ${sourceFilename}` : ""}
          </p>
          <ul className="mt-2 grid gap-1 sm:grid-cols-2">
            <li>Downpayment: £{openingOffer.downpayment.toLocaleString()}</li>
            <li>Interest rate: {openingOffer.interest_rate_pct}%</li>
            <li>Loan length: {openingOffer.loan_length_years} years</li>
            <li>
              Structure: {openingOffer.interest_structure}/10 (
              {structureLabel(openingOffer.interest_structure)})
            </li>
          </ul>
        </div>
      ) : null}
    </div>
  );
}
