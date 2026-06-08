import type { ReactNode } from "react";

export function ChartTooltip({
  active,
  label,
  payload,
  formatter,
}: {
  active?: boolean;
  label?: string | number;
  payload?: { name?: string; value?: number | string | [number, number]; color?: string; payload?: unknown }[];
  formatter?: (value: number | string, name?: string) => ReactNode;
}) {
  if (!active || payload === undefined || payload.length === 0) {
    return null;
  }

  return (
    <div className="border border-border bg-[#1e1e1e] p-3 text-sm">
      {label !== undefined ? <p className="mb-2 text-muted">{label}</p> : null}
      <div className="space-y-1">
        {payload.map((item, index) => {
          if (Array.isArray(item.value)) {
            return null;
          }
          return (
            <p className="font-mono text-ink" key={`${item.name ?? "value"}-${index}`}>
              <span className="mr-2 inline-block h-2 w-2" style={{ background: item.color }} />
              {item.name ? <span className="mr-2 text-muted">{item.name}</span> : null}
              {formatter ? formatter(item.value ?? "", item.name) : item.value}
            </p>
          );
        })}
      </div>
    </div>
  );
}
