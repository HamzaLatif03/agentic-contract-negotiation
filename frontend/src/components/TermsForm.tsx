import type { InitialPeriodYears, PartyTerms, PersonaSummary, RateType, RepaymentType } from "../types";

interface TermsFormProps {
  borrower: PartyTerms;
  lender: PartyTerms;
  personas: PersonaSummary[];
  selectedPersonaId: string;
  disabled: boolean;
  onBorrowerChange: (terms: PartyTerms) => void;
  onLenderChange: (terms: PartyTerms) => void;
  onPersonaChange: (personaId: string) => void;
  onSubmit: () => void;
}

const RANGE_FIELDS: { label: string; min: keyof PartyTerms; max: keyof PartyTerms }[] = [
  { label: "Deposit (£)", min: "min_downpayment", max: "max_downpayment" },
  { label: "Interest rate (%)", min: "min_interest_rate_pct", max: "max_interest_rate_pct" },
  { label: "Loan term (years)", min: "min_loan_length_years", max: "max_loan_length_years" },
  { label: "Arrangement fee (£)", min: "min_arrangement_fee", max: "max_arrangement_fee" },
  { label: "Cashback (£)", min: "min_cashback", max: "max_cashback" },
  {
    label: "Overpayment allowance (%)",
    min: "min_overpayment_allowance_pct",
    max: "max_overpayment_allowance_pct",
  },
  { label: "ERC during deal (%)", min: "min_erc_pct", max: "max_erc_pct" },
];

const FEATURE_PREFS: {
  key: "portable_preference" | "free_valuation_preference" | "free_legal_preference";
  label: string;
}[] = [
  { key: "portable_preference", label: "Portable mortgage" },
  { key: "free_valuation_preference", label: "Free valuation" },
  { key: "free_legal_preference", label: "Free legal work" },
];

function preferenceHint(value: number): string {
  if (value <= 3) return "prefer off / refuse";
  if (value <= 4) return "lean against";
  if (value <= 6) return "flexible — trade freely";
  if (value <= 8) return "lean toward on";
  return "must-have / strongly want";
}

function PartyFields({
  title,
  accentClass,
  terms,
  disabled,
  onChange,
}: {
  title: string;
  accentClass: string;
  terms: PartyTerms;
  disabled: boolean;
  onChange: (terms: PartyTerms) => void;
}) {
  const inputClass =
    "rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none ring-teal-500/30 focus:ring-2 disabled:opacity-50";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${accentClass}`} />
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
      </div>
      <div className="space-y-4">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Ranges</p>
        {RANGE_FIELDS.map(({ label, min, max }) => (
          <div key={label} className="space-y-1.5">
            <label className="text-xs font-medium text-slate-600">{label}</label>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                value={terms[min] as number}
                disabled={disabled}
                onChange={(e) => onChange({ ...terms, [min]: Number(e.target.value) })}
                className={inputClass}
                placeholder="Min"
              />
              <input
                type="number"
                value={terms[max] as number}
                disabled={disabled}
                onChange={(e) => onChange({ ...terms, [max]: Number(e.target.value) })}
                className={inputClass}
                placeholder="Max"
              />
            </div>
          </div>
        ))}

        <p className="pt-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          Product preferences
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1 text-xs text-slate-600">
            Rate type
            <select
              disabled={disabled}
              value={terms.preferred_rate_type}
              onChange={(e) =>
                onChange({ ...terms, preferred_rate_type: e.target.value as RateType })
              }
              className={`block w-full ${inputClass}`}
            >
              <option value="fixed">Fixed</option>
              <option value="tracker">Tracker</option>
              <option value="discount">Discount</option>
            </select>
          </label>
          <label className="space-y-1 text-xs text-slate-600">
            Initial deal period
            <select
              disabled={disabled}
              value={terms.preferred_initial_period_years}
              onChange={(e) =>
                onChange({
                  ...terms,
                  preferred_initial_period_years: Number(e.target.value) as InitialPeriodYears,
                })
              }
              className={`block w-full ${inputClass}`}
            >
              <option value={2}>2 years</option>
              <option value={5}>5 years</option>
              <option value={10}>10 years</option>
            </select>
          </label>
          <label className="space-y-1 text-xs text-slate-600 sm:col-span-2">
            Repayment type
            <select
              disabled={disabled}
              value={terms.preferred_repayment_type}
              onChange={(e) =>
                onChange({
                  ...terms,
                  preferred_repayment_type: e.target.value as RepaymentType,
                })
              }
              className={`block w-full ${inputClass}`}
            >
              <option value="capital_repayment">Capital repayment</option>
              <option value="interest_only">Interest only</option>
            </select>
          </label>
        </div>

        <p className="pt-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          Feature desire (1 = off · 5 = flexible · 10 = on)
        </p>
        <div className="space-y-3">
          {FEATURE_PREFS.map(({ key, label }) => (
            <label key={key} className="block space-y-1 text-sm text-slate-700">
              <div className="flex items-baseline justify-between gap-2">
                <span>{label}</span>
                <span className="text-xs tabular-nums text-slate-500">
                  {terms[key]}/10 — {preferenceHint(terms[key])}
                </span>
              </div>
              <input
                type="range"
                min={1}
                max={10}
                step={1}
                disabled={disabled}
                value={terms[key]}
                onChange={(e) => onChange({ ...terms, [key]: Number(e.target.value) })}
                className="w-full accent-teal-600 disabled:opacity-50"
              />
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function TermsForm({
  borrower,
  lender,
  personas,
  selectedPersonaId,
  disabled,
  onBorrowerChange,
  onLenderChange,
  onPersonaChange,
  onSubmit,
}: TermsFormProps) {
  const selected = personas.find((p) => p.id === selectedPersonaId);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">UK mortgage positions</h1>
          <p className="text-sm text-slate-500">
            Pick a persona scenario, then tweak ranges and feature desire before negotiating.
          </p>
        </div>
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled}
          className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700 disabled:opacity-50"
        >
          {disabled ? "Negotiating…" : "Start negotiation"}
        </button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="block space-y-1.5 text-sm text-slate-700">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Persona
          </span>
          <select
            disabled={disabled || personas.length === 0}
            value={selectedPersonaId}
            onChange={(e) => onPersonaChange(e.target.value)}
            className="block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none ring-teal-500/30 focus:ring-2 disabled:opacity-50"
          >
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.tag}
              </option>
            ))}
          </select>
        </label>
        {selected ? (
          <p className="mt-2 text-sm leading-relaxed text-slate-600">{selected.description}</p>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <PartyFields
          title="Borrower"
          accentClass="bg-blue-500"
          terms={borrower}
          disabled={disabled}
          onChange={onBorrowerChange}
        />
        <PartyFields
          title="Lender"
          accentClass="bg-violet-500"
          terms={lender}
          disabled={disabled}
          onChange={onLenderChange}
        />
      </div>
    </div>
  );
}
