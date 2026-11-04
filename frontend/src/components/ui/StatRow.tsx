import { StatCard } from "./StatCard";
import type { Stat } from "./types";
export type StatRowProps = { stats: Stat[] };
export function StatRow({ stats }: StatRowProps) {
  return <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
    {stats.map(stat => <StatCard key={stat.label} {...stat} />)}
  </div>;
}
