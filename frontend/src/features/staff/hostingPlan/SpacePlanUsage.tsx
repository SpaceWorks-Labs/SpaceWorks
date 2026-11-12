import { t } from "@lingui/core/macro";
import { Trans } from "@lingui/react/macro";
import { Callout, ErrorText, RelativeTime } from "../../../components/ui";
import { useSpacePlanUsage } from "./spacePlanApi";
import { LogoLoader } from "../../../components/LogoLoader";

/** The Space Manager's view of the hosting plan: its name, trial, read-only state and warnings (the rows are in SpaceLimitsUsage). */
export function SpacePlanUsage({ makerspaceId }: { makerspaceId: number }) {
  const query = useSpacePlanUsage(makerspaceId, true);
  if (query.isLoading) return <LogoLoader size={48} className="min-h-32 py-3" />;
  if (query.isError || !query.data) return <ErrorText resource={t`your hosting plan`} onRetry={() => { void query.refetch(); }} />;
  const data = query.data;
  if (data.hosted === false) return <section aria-labelledby="space-plan-title" className="grid gap-2 rounded-xl border border-line bg-panel p-4">
    <h3 id="space-plan-title" className="title-section">{t`Unlimited (own space)`}</h3>
    <p className="text-sm text-muted">{t`This space has no plan. Any limit the platform operator sets is listed under Limits by area.`}</p>
  </section>;
  return <section aria-labelledby="space-plan-title" className="grid gap-4 rounded-xl border border-line bg-panel p-4">
    <header className="grid gap-1">
      <h3 id="space-plan-title" className="title-section">{data.plan ? data.plan.name : t`No plan`}</h3>
      {data.plan?.description ? <p className="text-sm text-muted">{data.plan.description}</p> : null}
      {data.trial_ends_at ? <p className="text-sm text-ink"><Trans>Trial ends <RelativeTime date={data.trial_ends_at} exact /></Trans></p> : null}
    </header>
    {data.read_only_reason ? <Callout size="inline" tone="danger" lead={t`This space is read-only.`} body={data.read_only_reason} /> : null}
    {data.warnings.length ? <ul className="grid gap-2" aria-label={t`Plan warnings`}>
      {data.warnings.map(text => <li key={text}><Callout size="inline" tone="warn" lead={text} /></li>)}</ul> : null}
    <p className="text-sm text-muted">{t`Each limit's use is listed by area under Limits by area.`}</p>
  </section>;
}
