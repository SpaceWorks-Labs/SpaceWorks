export type ProgressBarProps = { value: number; label: string; tone?: "accent" | "warn" | "danger" };
const fills = { accent: "bg-accent", warn: "bg-warn", danger: "bg-danger" };
export function ProgressBar({ value, label, tone = "accent" }: ProgressBarProps) {
  const percent = Math.round(Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0)) * 100);
  return <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}
    className="h-1 overflow-hidden rounded-full bg-line">
    <div className={`h-full rounded-full ${fills[tone]}`} style={{ width: `${percent}%` }} />
  </div>;
}
