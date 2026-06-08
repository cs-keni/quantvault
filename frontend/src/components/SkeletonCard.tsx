export function SkeletonCard() {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="h-4 w-24 animate-pulse rounded bg-border" />
      <div className="mt-4 h-8 w-28 animate-pulse rounded bg-border" />
    </div>
  );
}

export function PageSkeleton() {
  return (
    <main className="min-h-screen bg-bg px-6 py-8">
      <div className="mx-auto grid max-w-7xl gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <SkeletonCard key={index} />
        ))}
      </div>
    </main>
  );
}
