import { useEffect, useState } from "react";

export type MetricTone = "neutral" | "positive" | "negative";

function useCountUp(value: number | null) {
  const [displayValue, setDisplayValue] = useState(value ?? 0);

  useEffect(() => {
    let animationId = 0;

    if (value === null) {
      animationId = window.requestAnimationFrame(() => setDisplayValue(0));
      return () => window.cancelAnimationFrame(animationId);
    }

    const targetValue = value;
    const startValue = 0;
    let frame = 0;
    const frames = 28;

    function tick() {
      frame += 1;
      const progress = Math.min(frame / frames, 1);
      const eased = 1 - (1 - progress) ** 3;
      setDisplayValue(startValue + (targetValue - startValue) * eased);
      if (progress < 1) {
        animationId = window.requestAnimationFrame(tick);
      }
    }

    animationId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(animationId);
  }, [value]);

  return displayValue;
}

export function MetricCard({
  label,
  value,
  formatter,
  tone = "neutral",
}: {
  label: string;
  value: number | null;
  formatter: (value: number) => string;
  tone?: MetricTone;
}) {
  const displayValue = useCountUp(value);
  const toneClass =
    tone === "positive" ? "text-positive" : tone === "negative" ? "text-negative" : "text-ink";

  return (
    <article className="rounded-lg border border-border bg-surface p-4">
      <p className="text-sm font-medium text-muted">{label}</p>
      <p className={`mt-3 font-mono text-2xl font-medium ${toneClass}`}>
        {value === null ? "—" : formatter(displayValue)}
      </p>
    </article>
  );
}
