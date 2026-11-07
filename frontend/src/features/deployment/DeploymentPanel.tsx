import { t } from "@lingui/core/macro";
import { SettingsRow } from "../../components/ui";
import { DeploymentNotices } from "./DeploymentNotices";
import { FreeQuotaPanel } from "./FreeQuotaPanel";
import { dateLabel, QuotaCard } from "./QuotaCard";
import type { DeploymentSummary, TenantDeploymentSummary } from "./types";

/** Mount inside the existing AppShell settings/health layout after server authorization. */
export function DeploymentPanel({ data }: { data: DeploymentSummary | TenantDeploymentSummary }) {
  return <section className="grid gap-4" aria-label={t`Deployment`}>
    <h2 className="text-lg font-semibold text-ink">{t`Deployment`}</h2>
    <DeploymentNotices data={data} />
    {data.scope === "tenant" ? <>
      {data.profile === "free" && data.objects?.scope === "tenant" ? <QuotaCard label={t`Your makerspace’s object storage`} sample={data.objects} /> : null}
      {data.deployment_warning ? <p className="text-sm text-warn-ink">{t`The deployment needs operator attention. Requests or scheduled work may be delayed; contact your operator.`}</p> : null}
    </> : <>
      <SettingsRow label={t`Launch mode`}>{data.mode} / {data.profile}</SettingsRow>
      <SettingsRow label={t`Process and scheduler topology`}>{data.topology}</SettingsRow>
      <SettingsRow label={t`Database`}>{t`PostgreSQL ${data.database_major}, ${data.database_transport}`}</SettingsRow>
      <SettingsRow label={t`Storage guarantees`}><ul className="grid gap-2">{data.storage.map((store, index) => <li key={index}>
        {store.label}: {store.upload === "post" ? t`POST upload-time size policy` : t`PUT finalization-time size validation`}{t`; ${store.versioned ? "versioned" : "unversioned"}; Object Lock ${store.object_lock ? "available" : "unavailable"}.`}</li>)}</ul></SettingsRow>
      <SettingsRow label={t`Scanner policy`}>{data.scanner === "clamav" ? t`ClamAV (fails closed on scan failure)` : t`None`}</SettingsRow>
      <SettingsRow label={t`Last successful work`}>{t`Worker: ${dateLabel(data.last_worker_success_at)}. Scheduler: ${dateLabel(data.last_scheduler_success_at)}.`}</SettingsRow>
      {data.mode === "managed" ? <SettingsRow label={t`Provider recovery`}>
        <p>{t`Database backup/PITR: ${data.provider_recovery?.database_status ?? "unknown"}. Object recovery: ${data.provider_recovery?.object_status ?? "unknown"}.`}</p>
        <p className="mt-2">{t`Offline recovery drill: ${data.provider_recovery?.drill_status ?? "unknown"}. Last drill: ${dateLabel(data.provider_recovery?.last_drill_at ?? null)}.`}</p>
        <p className="mt-2">{data.provider_recovery?.reason || t`Verify your provider plan’s recovery configuration and complete an offline drill.`} {t` Independent database and object recovery points may differ; escrow configuration and keys separately.`}</p>
        {safeRunbook(data.provider_recovery?.runbook_url) ? <a className="desk-link inline-flex min-h-11 items-center"
          href={data.provider_recovery?.runbook_url} target="_blank" rel="noreferrer">{t`Provider recovery runbook`}</a> : null}
      </SettingsRow> : null}
      <SettingsRow label={t`Backup capabilities`}>{data.mode === "host" ? t`Supervised host recovery follows the configured host contract.` : t`Deployment archives and in-place restore require a host supervisor.`}
        <p className="mt-2">{t`Portable tenant dump: `}{data.portable_dump_available ? t`Qualified; import into a fresh supervised target` : t`Unavailable on this deployment`}.</p>
        {!data.portable_dump_available ? <p className="mt-2">{data.portable_dump_reason || t`Direct/session maintenance, isolated scratch databases and capture proofs must pass before export.`}</p> : null}
        <a className="desk-link mt-2 inline-flex min-h-11 items-center" href="https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/docs/deploy/cloud-recovery.md" target="_blank" rel="noreferrer">{t`Recovery limitations and operator steps`}</a>
      </SettingsRow>
      {data.mode === "managed" ? <SettingsRow label={t`Platform updates`}>{t`Deploy through your cloud provider.`}</SettingsRow> : null}
      {data.profile === "free" && data.free_usage ? <FreeQuotaPanel usage={data.free_usage} /> : null}
    </>}
  </section>;
}

function safeRunbook(value?: string) {
  try { const url = new URL(value ?? ""); return url.protocol === "https:" && !url.username && !url.password; }
  catch { return false; }
}
