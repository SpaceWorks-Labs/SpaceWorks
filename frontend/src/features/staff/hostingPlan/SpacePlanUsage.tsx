import { t } from "@lingui/core/macro";
import { Callout, ErrorText, ProgressBar, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { usageAmount } from "../platformMonitoringApi";
import { useSpacePlanUsage, type PlanLevel } from "./spacePlanApi";

const LEVEL: Record<PlanLevel, { label: string; tone: "accent" | "warn" | "danger" } | null> = {
  ok: null, warning: { label: t`Near limit`, tone: "warn" }, limit: { label: t`At limit`, tone: "danger" },
};

/** The Space Manager's view of the hosting plan: each limit as a bar, warning at 80 %, refused at 100 %. */
export function SpacePlanUsage({ makerspaceId }: { makerspaceId: number }) {
  const query = useSpacePlanUsage(makerspaceId, true);
  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError || !query.data) return <ErrorText resource="your hosting plan" onRetry={() => { void query.refetch(); }} />;
  const data = query.data;
  return <section aria-labelledby="space-plan-title" className="grid gap-4 rounded-xl border border-line bg-panel p-4">
    <header className="grid gap-1">
      <h3 id="space-plan-title" className="title-section">{data.plan ? data.plan.name : t`Fair-use defaults`}</h3>
      {data.plan?.description ? <p className="text-sm text-muted">{data.plan.description}</p> : null}
      {data.trial_ends_at ? <p className="text-sm text-ink">{t`Trial ends `}<RelativeTime date={data.trial_ends_at} exact /></p> : null}
    </header>
    {data.read_only_reason ? <Callout size="inline" tone="danger" lead="This space is read-only." body={data.read_only_reason} /> : null}
    {data.warnings.length ? <ul className="grid gap-2" aria-label={t`Plan warnings`}>
      {data.warnings.map(text => <li key={text}><Callout size="inline" tone="warn" lead={text} /></li>)}</ul> : null}
    <div className="grid gap-4 sm:grid-cols-2">
      {data.resources.map(row => {
        const level = LEVEL[row.level];
        return <div key={row.key} className="grid gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-semibold text-ink">{row.label}</span>
            {level ? <StatusPill label={level.label} tone={level.tone === "danger" ? "danger" : "warn"} /> : null}
          </div>
          <p className="text-sm text-muted">{usageAmount(row.used, row.unit)} of {row.limit === null ? t`Unlimited` : usageAmount(row.limit, row.unit)}
            {row.percent !== null ? ` · ${Math.round(row.percent)}%` : ""}</p>
          {row.percent !== null ? <ProgressBar value={row.percent / 100} label={`${row.label} used`} tone={level?.tone ?? "accent"} /> : null}
        </div>;
      })}
    </div>
  </section>;
}
