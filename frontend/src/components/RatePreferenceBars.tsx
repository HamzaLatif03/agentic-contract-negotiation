interface RatePreferenceBarsProps {
  fixedLabel: string;
  variableLabel: string;
  fixed: number;
  variable: number;
  disabled: boolean;
  onFixedChange: (value: number) => void;
  onVariableChange: (value: number) => void;
}

function PreferenceSlider({
  label,
  value,
  accentClass,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  accentClass: string;
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  const clamp = (n: number) => Math.max(1, Math.min(10, n));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {label}
        </label>
        <span className="text-xs font-semibold text-slate-600">{value}/10</span>
      </div>
      <input
        type="range"
        min={1}
        max={10}
        step={1}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(clamp(Number(e.target.value)))}
        className={`w-full disabled:opacity-50 ${accentClass}`}
      />
    </div>
  );
}

export default function RatePreferenceBars({
  fixedLabel,
  variableLabel,
  fixed,
  variable,
  disabled,
  onFixedChange,
  onVariableChange,
}: RatePreferenceBarsProps) {
  return (
    <div className="space-y-4">
      <PreferenceSlider
        label={fixedLabel}
        value={fixed}
        accentClass="accent-blue-600"
        disabled={disabled}
        onChange={onFixedChange}
      />
      <PreferenceSlider
        label={variableLabel}
        value={variable}
        accentClass="accent-violet-600"
        disabled={disabled}
        onChange={onVariableChange}
      />
    </div>
  );
}
