export type Period = "1mo" | "6mo" | "1y" | "2y" | "max";

const periods: Period[] = ["1mo", "6mo", "1y", "2y", "max"];

export function PeriodToggle({
  value,
  onChange,
}: {
  value: Period;
  onChange: (period: Period) => void;
}) {
  return (
    <div className="grid grid-cols-5 rounded-md border border-border bg-surface p-1">
      {periods.map((period) => (
        <button
          className={`h-8 min-w-12 rounded px-2 text-xs font-semibold transition ${
            value === period
              ? "bg-bg text-accent ring-1 ring-border"
              : "text-muted hover:text-ink"
          }`}
          key={period}
          type="button"
          onClick={() => onChange(period)}
        >
          {period}
        </button>
      ))}
    </div>
  );
}
