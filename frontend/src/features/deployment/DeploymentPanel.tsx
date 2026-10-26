import { SettingsRow } from "../../components/ui";
import { DeploymentNotices } from "./DeploymentNotices";
import { FreeQuotaPanel } from "./FreeQuotaPanel";
import { dateLabel, QuotaCard } from "./QuotaCard";
import type { DeploymentSummary, TenantDeploymentSummary } from "./types";

/** Mount inside the existing AppShell settings/health layout after server authorization. */
export function DeploymentPanel({ data }: { data: DeploymentSummary | TenantDeploymentSummary }) {
  return <section className="grid gap-4" aria-label="Deployment">
    <h2 className="text-lg font-semibold text-ink">Deployment</h2>
    <DeploymentNotices data={data} />
    {data.scope === "tenant" ? <>
      {data.profile === "free" && data.objects?.scope === "tenant" ? <QuotaCard label="Your makerspace’s object storage" sample={data.objects} /> : null}
      {data.deployment_warning ? <p className="text-sm text-warn-ink">The deployment needs operator attention. Requests or scheduled work may be delayed; contact your operator.</p> : null}
    </> : <>
      <SettingsRow label="Launch mode">{data.mode} / {data.profile}</SettingsRow>
      <SettingsRow label="Process and scheduler topology">{data.topology}</SettingsRow>
      <SettingsRow label="Database">PostgreSQL {data.database_major}, {data.database_transport}</SettingsRow>
      <SettingsRow label="Storage guarantees"><ul className="grid gap-2">{data.storage.map((store, index) => <li key={index}>
        {store.label}: {store.upload === "post" ? "POST upload-time size policy" : "PUT finalization-time size validation"}; {store.versioned ? "versioned" : "unversioned"}; Object Lock {store.object_lock ? "available" : "unavailable"}.
      </li>)}</ul></SettingsRow>
      <SettingsRow label="Scanner policy">{data.scanner === "clamav" ? "ClamAV (fails closed on scan failure)" : "None"}</SettingsRow>
      <SettingsRow label="Last successful work">Worker: {dateLabel(data.last_worker_success_at)}. Scheduler: {dateLabel(data.last_scheduler_success_at)}.</SettingsRow>
      {data.mode === "managed" ? <SettingsRow label="Provider recovery">
        <p>Database backup/PITR: {data.provider_recovery?.database_status ?? "unknown"}. Object recovery: {data.provider_recovery?.object_status ?? "unknown"}.</p>
        <p className="mt-2">Offline recovery drill: {data.provider_recovery?.drill_status ?? "unknown"}. Last drill: {dateLabel(data.provider_recovery?.last_drill_at ?? null)}.</p>
        <p className="mt-2">{data.provider_recovery?.reason || "Verify your provider plan’s recovery configuration and complete an offline drill."} Independent database and object recovery points may differ; escrow configuration and keys separately.</p>
        {safeRunbook(data.provider_recovery?.runbook_url) ? <a className="desk-link inline-flex min-h-11 items-center"
          href={data.provider_recovery?.runbook_url} target="_blank" rel="noreferrer">Provider recovery runbook</a> : null}
      </SettingsRow> : null}
      <SettingsRow label="Backup capabilities">{data.mode === "host" ? "Supervised host recovery follows the configured host contract." : "Deployment archives and in-place restore require a host supervisor."}
        <p className="mt-2">Portable tenant dump: {data.portable_dump_available ? "Qualified; import into a fresh supervised target" : "Unavailable on this deployment"}.</p>
        {!data.portable_dump_available ? <p className="mt-2">{data.portable_dump_reason || "Direct/session maintenance, isolated scratch databases and capture proofs must pass before export."}</p> : null}
        <a className="desk-link mt-2 inline-flex min-h-11 items-center" href="https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/docs/deploy/cloud-recovery.md" target="_blank" rel="noreferrer">Recovery limitations and operator steps</a>
      </SettingsRow>
      {data.mode === "managed" ? <SettingsRow label="Platform updates">Deploy through your cloud provider.</SettingsRow> : null}
      {data.profile === "free" && data.free_usage ? <FreeQuotaPanel usage={data.free_usage} /> : null}
    </>}
  </section>;
}

function safeRunbook(value?: string) {
  try { const url = new URL(value ?? ""); return url.protocol === "https:" && !url.username && !url.password; }
  catch { return false; }
}
