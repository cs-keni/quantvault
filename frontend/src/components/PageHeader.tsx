export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="border-b border-border pb-6">
      <p className="text-xs font-semibold uppercase text-accent">QuantVault</p>
      <h1 className="mt-2 text-2xl font-semibold text-ink">{title}</h1>
      {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
    </div>
  );
}
