interface PlaceholderPageProps {
  title: string;
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <main className="min-h-screen bg-bg px-6 py-8">
      <section className="mx-auto max-w-6xl">
        <div className="border-b border-ink/10 pb-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-accent">QuantVault</p>
          <h1 className="mt-2 text-2xl font-semibold text-ink">{title}</h1>
        </div>
      </section>
    </main>
  );
}
