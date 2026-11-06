import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Callout, StatusPill } from "../../components/ui";
import { dateLabel, QuotaCard } from "./QuotaCard";
import type { FreeUsage } from "./types";

export function FreeQuotaPanel({ usage }: { usage: FreeUsage }) {
  const [now, setNow] = useState(Date.now);
  const [receivedAt, setReceivedAt] = useState(Date.now);
  useEffect(() => { setReceivedAt(Date.now()); setNow(Date.now()); }, [usage]);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  const completed = usage.tick.last_completed_at ? Date.parse(usage.tick.last_completed_at) : NaN;
  const interval = usage.tick.interval_seconds;
  // The server measures age at request time. Add time spent on this screen rather
  // than assuming the operator's clock agrees with the database clock.
  const serverAge = usage.tick.age_seconds;
  const seconds = Number.isFinite(completed) && serverAge !== null && Number.isFinite(serverAge) && serverAge >= 0
    ? serverAge + Math.max(0, now - receivedAt) / 1000 : null;
  const age = seconds === null ? null : Math.floor(seconds / 60);
  const stale = usage.tick.state === "unknown" || usage.tick.state === "never" || seconds === null
    || !Number.isFinite(interval) || interval <= 0 || seconds > interval * 3;
  const tickLabel = usage.tick.state === "never" && !usage.tick.last_completed_at ? "Never run"
    : age === null || usage.tick.state === "unknown" ? "Unknown completion" : stale ? "Overdue" : "Recent completion";
  return <section className="grid gap-4" aria-label={t`Free hosting usage`}>
    <div className="grid gap-3 @2xl:grid-cols-3">
      {usage.visibility === "deployment" && usage.database ? <QuotaCard label={t`Database usage`} sample={usage.database} /> : null}
      {usage.visibility === "deployment" || usage.objects.scope === "tenant" ? <QuotaCard label={t`Object storage usage`} sample={usage.objects} /> : null}
      {usage.visibility === "deployment" || usage.email.scope === "tenant" ? <QuotaCard label={t`Email accepted today`} sample={usage.email} /> : null}
    </div>
    <p className="text-sm text-muted">{t`Application totals may omit other workloads on a shared provider account. Pending email: `}{usage.visibility === "deployment" || usage.email.scope === "tenant" ? usage.email_pending ?? t`Unknown` : t`Contact your operator`}. Uncertain email: {usage.visibility === "deployment" || usage.email.scope === "tenant" ? usage.email_uncertain ?? t`Unknown` : t`Contact your operator`}. Check the provider account for its reset timezone and monthly allowance. Accepted sends are distinct from inbox delivery; uncertain sends remain reserved.</p>
    {usage.email_accounts?.map((account) => <div key={account.label} className="rounded-xl border border-line bg-panel p-4 text-sm">
      <h3 className="font-semibold">{account.label} ({account.provider})</h3>
      <p>{t`Accepted today: ${account.accepted}. Reserved: ${account.reserved}. Uncertain: ${account.uncertain}.`}</p>
      <p>{t`Daily cap: `}{account.daily_cap ?? t`Unknown`}. Month charged: {account.monthly_charged} / {account.monthly_cap ?? t`Unknown`}. Reset timezone: {account.reset_timezone}.</p>
      <p className="text-muted">{t`Other provider workloads: `}{account.provider_usage_known ? t`Included` : t`Unknown; check the provider account`}.</p>
    </div>)}
    {(usage.notification_uncertain ?? 0) > 0 ? <Callout size="inline" tone="warn" lead="Some notification outcomes are uncertain."
      body={`${usage.notification_uncertain} delivery claims need operator review with provider evidence. Elapsed time cannot prove they were not accepted.`} /> : null}
    <div className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center gap-3"><h3 className="font-semibold text-ink">{t`Scheduled work`}</h3>
        <StatusPill tone={stale ? "warn" : "neutral"} label={tickLabel} /></div>
      <p className="mt-2 text-sm text-ink">{t`Minutes since last successful tick: `}{age ?? t`Unknown`}. Configured interval: {interval > 0 ? `${interval / 60} minutes` : t`Unknown`}.</p>
      <p className="mt-1 text-sm text-muted">{t`Last trigger contact: ${dateLabel(usage.tick.last_contact_at)}. Failed tasks: `}{usage.tick.failed_tasks ?? t`Unknown`}.</p>
      {stale ? <p className="mt-2 text-sm text-ink">{t`Ask the operator to check the trigger, provider pause status and job failures. Contact alone does not prove successful progress.`}</p> : null}
    </div>
    {(usage.tick.failed_tasks ?? 0) > 0 ? <Callout size="inline" tone="danger" lead="Some scheduled work failed."
      body="Review job failures and backlog even if the trigger connected recently." /> : null}
  </section>;
}
