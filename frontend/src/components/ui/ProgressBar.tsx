export type ProgressBarProps = { value: number; label: string };
export function ProgressBar({ value, label }: ProgressBarProps) {
  const percent = Math.round(Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0)) * 100);
  return <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}
    className="h-1 overflow-hidden rounded-full bg-line">
    <div className="h-full rounded-full bg-accent" style={{ width: `${percent}%` }} />
  </div>;
}
