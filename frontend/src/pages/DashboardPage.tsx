export function DashboardPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-bg px-6 text-center">
      <div className="animate-in fade-in slide-in-from-bottom-2 flex flex-col items-center gap-4 duration-500">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent text-lg font-semibold text-white shadow-sm shadow-accent/30">
          QV
        </span>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">QuantVault</h1>
          <p className="mt-1 text-sm text-ink/60">
            Portfolio scaffold is up — Phase 1 (auth + domain models) lands next.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full bg-surface px-4 py-1.5 text-xs font-medium text-ink/70 ring-1 ring-ink/5">
          <span className="h-1.5 w-1.5 rounded-full bg-positive" />
          Frontend connected
        </div>
      </div>
    </main>
  );
}
