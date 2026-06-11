import type { ReactNode } from "react";

export function PageHeader({ title, subtitle }: { title: string; subtitle?: ReactNode }) {
  return (
    <div className="border-b border-border pb-6">
      <h1 className="text-2xl font-semibold text-ink">{title}</h1>
      {subtitle ? <div className="mt-1 text-sm text-muted">{subtitle}</div> : null}
    </div>
  );
}
