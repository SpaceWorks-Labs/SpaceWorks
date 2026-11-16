import { StatCard } from "./StatCard";
export type MetricProps = { label: string; value?: string | number; danger?: boolean };
export function Metric({ label, value, danger = false }: MetricProps) {
  return <StatCard label={label} value={value ?? 0} tone={danger ? "danger" : "neutral"} />;
}
