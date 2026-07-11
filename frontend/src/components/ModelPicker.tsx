export interface CatalogModel {
  id: string;
  label: string;
  runtime?: "api" | "ollama";
  ollama_name?: string;
  description: string;
  available: boolean;
  resolved_name: string;
}

interface ModelPickerProps {
  catalog: CatalogModel[];
  selected: string;
  defaultModel: string | null;
  disabled: boolean;
  loading: boolean;
  error: string | null;
  onChange: (ollamaName: string) => void;
  onRefresh: () => void;
}

export default function ModelPicker({
  catalog,
  selected,
  defaultModel,
  disabled,
  loading,
  error,
  onChange,
  onRefresh,
}: ModelPickerProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Models</h2>
          <p className="mt-1 text-sm text-slate-500">Ordered by approximate size (smallest first).</p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={disabled || loading}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error && (
        <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {error}
        </p>
      )}

      <div className="space-y-2">
        {catalog.map((entry) => {
          const value = entry.resolved_name;
          const checked = selected === value || selected === entry.ollama_name;
          return (
            <label
              key={entry.id}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 text-sm transition ${
                checked
                  ? "border-teal-300 bg-teal-50/70"
                  : "border-slate-200 bg-white hover:bg-slate-50"
              } ${!entry.available || disabled ? "opacity-60" : ""}`}
            >
              <input
                type="radio"
                className="mt-1"
                name="comparison-model"
                value={value}
                checked={checked}
                disabled={disabled || loading || !entry.available}
                onChange={() => onChange(value)}
              />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-slate-800">{entry.label}</span>
                  {!entry.available && (
                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                      {entry.runtime === "ollama" ? "Unavailable" : "Needs key"}
                    </span>
                  )}
                  {defaultModel === value && (
                    <span className="text-[10px] uppercase tracking-wide text-slate-400">
                      default
                    </span>
                  )}
                </span>
                <span className="mt-0.5 block text-xs text-slate-500">{entry.description}</span>
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
