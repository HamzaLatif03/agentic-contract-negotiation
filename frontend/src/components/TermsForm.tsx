import type { ReactNode } from "react";
import type { BorrowerTerms, LenderTerms } from "../types";
import RatePreferenceBars from "./RatePreferenceBars";

interface TermsFormProps {
  borrower: BorrowerTerms;
  lender: LenderTerms;
  disabled: boolean;
  onBorrowerChange: (terms: BorrowerTerms) => void;
  onLenderChange: (terms: LenderTerms) => void;
  onLoadDemo: () => void;
  onSubmit: () => void;
}

function RangeField({
  label,
  min,
  max,
  onMinChange,
  onMaxChange,
  disabled,
}: {
  label: string;
  min: number;
  max: number;
  onMinChange: (value: number) => void;
  onMaxChange: (value: number) => void;
  disabled: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </label>
      <div className="grid grid-cols-2 gap-2">
        <input
          type="number"
          value={min}
          disabled={disabled}
          onChange={(e) => onMinChange(Number(e.target.value))}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none ring-teal-500/30 focus:ring-2 disabled:opacity-50"
          placeholder="Min"
        />
        <input
          type="number"
          value={max}
          disabled={disabled}
          onChange={(e) => onMaxChange(Number(e.target.value))}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none ring-teal-500/30 focus:ring-2 disabled:opacity-50"
          placeholder="Max"
        />
      </div>
    </div>
  );
}

function PartyPanel({
  title,
  accentClass,
  children,
}: {
  title: string;
  accentClass: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${accentClass}`} />
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
      </div>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

export default function TermsForm({
  borrower,
  lender,
  disabled,
  onBorrowerChange,
  onLenderChange,
  onLoadDemo,
  onSubmit,
}: TermsFormProps) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Starting positions</h1>
          <p className="text-sm text-slate-500">
            Set acceptable ranges and rate preferences for each party before negotiation begins.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onLoadDemo}
            disabled={disabled}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
          >
            Load demo
          </button>
          <button
            type="button"
            onClick={onSubmit}
            disabled={disabled}
            className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700 disabled:opacity-50"
          >
            {disabled ? "Negotiating…" : "Start negotiation"}
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <PartyPanel title="Borrower" accentClass="bg-blue-500">
          <RangeField
            label="Downpayment (£)"
            min={borrower.min_downpayment}
            max={borrower.max_downpayment}
            disabled={disabled}
            onMinChange={(v) => onBorrowerChange({ ...borrower, min_downpayment: v })}
            onMaxChange={(v) => onBorrowerChange({ ...borrower, max_downpayment: v })}
          />
          <RangeField
            label="Interest rate (%)"
            min={borrower.min_interest_rate_pct}
            max={borrower.max_interest_rate_pct}
            disabled={disabled}
            onMinChange={(v) =>
              onBorrowerChange({ ...borrower, min_interest_rate_pct: v })
            }
            onMaxChange={(v) =>
              onBorrowerChange({ ...borrower, max_interest_rate_pct: v })
            }
          />
          <RangeField
            label="Loan length (years)"
            min={borrower.min_loan_length_years}
            max={borrower.max_loan_length_years}
            disabled={disabled}
            onMinChange={(v) =>
              onBorrowerChange({ ...borrower, min_loan_length_years: v })
            }
            onMaxChange={(v) =>
              onBorrowerChange({ ...borrower, max_loan_length_years: v })
            }
          />
          <RatePreferenceBars
            fixedLabel="Fixed rate preference"
            variableLabel="Variable rate preference"
            fixed={borrower.fixed_preference}
            variable={borrower.variable_preference}
            disabled={disabled}
            onFixedChange={(v) => onBorrowerChange({ ...borrower, fixed_preference: v })}
            onVariableChange={(v) =>
              onBorrowerChange({ ...borrower, variable_preference: v })
            }
          />
        </PartyPanel>

        <PartyPanel title="Lender" accentClass="bg-violet-500">
          <RangeField
            label="Downpayment (£)"
            min={lender.min_downpayment}
            max={lender.max_downpayment}
            disabled={disabled}
            onMinChange={(v) => onLenderChange({ ...lender, min_downpayment: v })}
            onMaxChange={(v) => onLenderChange({ ...lender, max_downpayment: v })}
          />
          <RangeField
            label="Interest rate (%)"
            min={lender.min_interest_rate_pct}
            max={lender.max_interest_rate_pct}
            disabled={disabled}
            onMinChange={(v) =>
              onLenderChange({ ...lender, min_interest_rate_pct: v })
            }
            onMaxChange={(v) =>
              onLenderChange({ ...lender, max_interest_rate_pct: v })
            }
          />
          <RangeField
            label="Loan length (years)"
            min={lender.min_loan_length_years}
            max={lender.max_loan_length_years}
            disabled={disabled}
            onMinChange={(v) =>
              onLenderChange({ ...lender, min_loan_length_years: v })
            }
            onMaxChange={(v) =>
              onLenderChange({ ...lender, max_loan_length_years: v })
            }
          />
          <RatePreferenceBars
            fixedLabel="Fixed rate preference"
            variableLabel="Variable rate preference"
            fixed={lender.fixed_preference}
            variable={lender.variable_preference}
            disabled={disabled}
            onFixedChange={(v) => onLenderChange({ ...lender, fixed_preference: v })}
            onVariableChange={(v) =>
              onLenderChange({ ...lender, variable_preference: v })
            }
          />
        </PartyPanel>
      </div>
    </div>
  );
}
