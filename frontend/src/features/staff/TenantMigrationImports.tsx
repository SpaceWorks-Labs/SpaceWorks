import { t } from "@lingui/core/macro";
import { useState } from "react";
import { DangerZone } from "../../components/ui";
import { useMigrationConfirmation } from "./MigrationConfirmation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  abortTarget,
  activateTarget,
  getImport,
  getVerification,
  listImports,
  runImport,
  tenantMigrationKeys,
  type ImportJob,
  type Pairing,
  type ReceiptEnvelope,
  type VerificationReport,
} from "./tenantMigrationApi";
import { TenantMigrationIdentityDecisions } from "./TenantMigrationIdentityDecisions";
import { ImportUploadResume, useImportArchiveUpload } from "./TenantMigrationUpload";
import { ErrorText, parseReceipt, ReceiptOutput, StatusPill } from "./tenantMigrationUi";

export function TenantMigrationImports({ pairings, active = true, phase = "import" }: { pairings: Pairing[]; active?: boolean; phase?: "import" | "verify" | "cutover" }) {
  const [archive, setArchive] = useState<File | null>(null);
  const [digest, setDigest] = useState("");
  const imports = useQuery({
    queryKey: tenantMigrationKeys.imports,
    queryFn: listImports,
  });
  const { upload: create, activeJobId } = useImportArchiveUpload();

  return (
    <>
      {active && phase === "import" ? <section aria-labelledby="migration-import-title" className="min-w-0">
      <p className="eyebrow">{t`Target deployment`}</p>
      <h3 className="title-section" id="migration-import-title">{t`Import and verify target`}</h3>
      <p className="mt-2 text-sm text-ink">{t`Upload the encrypted archive (age format) and bind it to the digest shown on the source export. Materialization creates an IMPORTING space; it is not live until separately activated.`}</p>
      <div className="mt-3 grid gap-3 @xl:grid-cols-2">
        <label className="text-sm text-ink">{t`Encrypted archive`}<input className="desk-input mt-1 w-full" type="file" onChange={(event) => setArchive(event.target.files?.[0] ?? null)} /></label>
        <label className="text-sm text-ink">{t`Source archive digest`}<input className="desk-input mt-1 w-full code-text" value={digest} onChange={(event) => setDigest(event.target.value)} /></label>
      </div>
      <button className="desk-button-primary mt-3" type="button" disabled={!archive || !digest.trim() || create.isPending} onClick={() => {
        if (archive) create.mutate({ file: archive, sourceArchiveDigest: digest.trim() });
      }}>
        {create.isPending ? t`Uploading encrypted archive…` : t`Create target import`}
      </button>
      <ErrorText error={create.error} field="source_archive_digest" />
      </section> : null}
      {active && imports.isLoading ? <p className="mt-4 text-sm text-muted">{t`Loading import jobs…`}</p> : null}
      {active ? <ErrorText error={imports.error} /> : null}
      <div className="grid gap-4">
        {(imports.data ?? []).map((job) => (
          <ImportJobCard job={job} key={job.id} drivingUpload={activeJobId === job.id} pairing={pairings.find((item) => item.migration_id === job.id)} active={active} phase={phase} />
        ))}
      </div>
    </>
  );
}

function ImportJobCard({ job: listedJob, pairing, drivingUpload, active, phase }: { job: ImportJob; pairing?: Pairing; drivingUpload: boolean; active: boolean; phase: "import" | "verify" | "cutover" }) {
  const client = useQueryClient();
  const [confirmCutover, confirmation] = useMigrationConfirmation();
  const [targetName, setTargetName] = useState("");
  const [targetSlug, setTargetSlug] = useState("");
  const [reviewedIdentities, setReviewedIdentities] = useState(false);
  const [sourceReceiptText, setSourceReceiptText] = useState("");
  const detail = useQuery({
    queryKey: tenantMigrationKeys.import(listedJob.id),
    queryFn: () => getImport(listedJob.id),
    refetchInterval: (query) => importRunning((query.state.data as ImportJob | undefined) ?? listedJob) ? 1500 : false,
  });
  const job = detail.data ?? listedJob;
  const sourceReceipt = parseReceipt(sourceReceiptText);
  const tenantName = targetName.trim() || job.source_makerspace_name || "imported tenant";
  const verification = useQuery({
    queryKey: tenantMigrationKeys.verification(job.id),
    queryFn: () => getVerification(job.id),
    enabled: job.status === "completed",
    retry: false,
  });
  const refreshJob = (next?: ImportJob) => {
    if (next) client.setQueryData(tenantMigrationKeys.import(job.id), next);
    client.invalidateQueries({ queryKey: tenantMigrationKeys.imports });
    client.invalidateQueries({ queryKey: tenantMigrationKeys.import(job.id) });
  };
  const run = useMutation({
    mutationFn: () => runImport(job.id, {
      target_identity: {
        ...(targetName.trim() ? { name: targetName.trim() } : {}),
        ...(targetSlug.trim() ? { slug: targetSlug.trim() } : {}),
      },
    }),
    onSuccess: refreshJob,
  });
  const activate = useMutation({
    mutationFn: (receipt: ReceiptEnvelope) => activateTarget(job.id, pairing!.id, { receipt }),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: tenantMigrationKeys.imports }),
        client.invalidateQueries({ queryKey: tenantMigrationKeys.import(job.id) }),
        client.invalidateQueries({ queryKey: tenantMigrationKeys.verification(job.id) }),
        client.invalidateQueries({ queryKey: ["staff", "makerspaces"] }),
      ]);
    },
  });
  const abort = useMutation({
    mutationFn: () => abortTarget(job.id, pairing!.id),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: tenantMigrationKeys.imports }),
        client.invalidateQueries({ queryKey: tenantMigrationKeys.import(job.id) }),
        client.invalidateQueries({ queryKey: ["staff", "makerspaces"] }),
      ]);
    },
  });
  const cutoverPending = activate.isPending || abort.isPending;
  const importFinalizing = job.status === "materializing" || job.status === "finalizing";
  const lifecycle = job.target_lifecycle_state?.toUpperCase()
    ?? (importFinalizing ? "IMPORTING" : (job.status ?? "pending").toUpperCase());
  const tone: "success" | "danger" | "warn" = lifecycle === "ACTIVE" ? "success" : lifecycle === "ABORTED" || job.status === "failed" ? "danger" : "warn";

  return (
    <>
    {active ? <article className="rounded-md border border-line bg-surface p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-ink">{job.source_makerspace_name || t`Pending archive inspection`}</p>
          <p className="mt-1 tabular-nums text-xs text-muted">{t`Import ${job.id}`}</p>
        </div>
        <StatusPill tone={tone}>{lifecycle}</StatusPill>
      </div>
      {job.status === "pending" ? <p className="mt-2 text-sm text-warn-ink">{t`Decrypting and verifying the encrypted archive in the background. Identity decisions appear when it finishes.`}</p> : null}
      {job.status === "uploading" ? <ImportUploadResume job={job} driving={drivingUpload} /> : null}
      {lifecycle === "IMPORTING" ? <p className="mt-2 text-sm text-warn-ink">{importFinalizing ? t`Import finalization is still running. The space is not active.` : t`Materialized and verified, but not activated. The space remains IMPORTING.`}</p> : null}
      {lifecycle === "ACTIVE" ? <p className="mt-2 text-sm text-success-ink">{t`Target is ACTIVE. The source switch-over receipt was consumed.`}</p> : null}
      {lifecycle === "ABORTED" ? <p className="mt-2 text-sm text-danger">{t`Target is ABORTED. Transfer its signed abort receipt to recover the archived source.`}</p> : null}
      {job.failure_detail ? <p className="mt-2 text-sm text-danger" role="alert">{job.failure_detail}</p> : null}
      <ErrorText error={detail.error} />
      <p className="mt-2 text-xs text-muted">{job.source_retention_notice}</p>
      {job.source_deployment_identity && typeof job.source_deployment_identity === "object" ? (
        <div className="mt-2"><p className="text-xs font-semibold text-ink">{t`Archived source deployment identity`}</p><pre className="mt-1 overflow-auto rounded border border-line bg-bg p-2 text-xs text-muted">{JSON.stringify(job.source_deployment_identity, null, 2)}</pre></div>
      ) : null}

      {phase !== "import" && job.status === "completed" ? (
        <VerificationReportView report={verification.data} loading={verification.isLoading} error={verification.error} />
      ) : null}
      {phase === "cutover" && job.status === "completed" && pairing && lifecycle === "IMPORTING" ? (
        <div className="mt-3 rounded-md border border-danger-line bg-panel p-3">
          <h4 className="title-section">{t`One-way target switch-over`}</h4>
          <p className="mt-1 text-sm text-ink">{t`Activation and abort are mutually exclusive. Activation cannot be undone from this screen.`}</p>
          <label className="mt-2 block text-sm text-ink">{t`Source switch-over receipt`}<textarea className="desk-input mt-1 min-h-28 w-full code-text text-base md:text-xs" value={sourceReceiptText} onChange={(event) => setSourceReceiptText(event.target.value)} /></label>
          <DangerZone title={t`Activate target ${tenantName}`} consequence={t`Activation consumes the source switch-over receipt and cannot be undone from this screen.`}
            action={{ label: t`Activate target ${tenantName}`, disabled: !sourceReceipt || !verification.data || cutoverPending, disabledReason: t`Add a valid source receipt and wait for verification before activating.`, pending: activate.isPending, pendingLabel: t`Activating target…`,
              onClick: () => { if (sourceReceipt) confirmCutover({ title: t`Activate target ${tenantName}`, name: tenantName, consequence: t`This target switch-over cannot be undone from this screen.`, onConfirm: () => activate.mutate(sourceReceipt) }); } }} />
          <DangerZone title={t`Abort target ${tenantName}`} consequence={t`Imported target objects will be rolled back. Transfer the signed abort receipt to recover the source.`}
            action={{ label: t`Abort target ${tenantName}`, disabled: cutoverPending, disabledReason: t`Wait for the current switch-over action.`, pending: abort.isPending, pendingLabel: t`Aborting target…`,
              onClick: () => confirmCutover({ title: t`Abort target ${tenantName}`, name: tenantName, consequence: t`Imported target objects will be rolled back.`, onConfirm: () => abort.mutate() }) }} />
        </div>
      ) : null}
      {job.status === "completed" && !pairing ? <p className="mt-3 text-sm text-warn-ink">{t`Link the matching server pairing before switch-over actions become available.`}</p> : null}
      <ErrorText error={activate.error ?? abort.error} field="receipt" />
      {confirmation}
      <ReceiptOutput label={t`Target abort receipt — transfer to source`} receipt={abort.data?.receipt} />
    </article> : null}
    {/* Materialising attests to these decisions, so the verify step shows them right above it. */}
    <TenantMigrationIdentityDecisions job={job} active={active && phase !== "cutover" && (job.status === "awaiting_identity" || job.status === "ready")} />
    {active && phase === "verify" && job.status === "ready" ? (
      <div className="mt-3 rounded-md border border-line bg-bg p-3">
        <h4 className="title-section">{t`Materialize target`}</h4>
        <div className="mt-2 grid gap-3 @xl:grid-cols-2">
          <label className="text-sm text-ink">{t`Target space name (optional)`}<input className="desk-input mt-1 w-full" value={targetName} onChange={(event) => setTargetName(event.target.value)} /></label>
          <label className="text-sm text-ink">{t`Target space slug (optional)`}<input className="desk-input mt-1 w-full" value={targetSlug} onChange={(event) => setTargetSlug(event.target.value)} /></label>
        </div>
        <label className="mt-2 flex min-h-11 items-center gap-2 text-sm text-ink">
          <input className="h-5 w-5 accent-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" type="checkbox" checked={reviewedIdentities} onChange={(event) => setReviewedIdentities(event.target.checked)} />
          {t`I reviewed every per-person identity decision shown above or in its prior review record.`}</label>
        <button className="desk-button-primary mt-3" type="button" disabled={!reviewedIdentities || run.isPending} onClick={() => run.mutate()}>{run.isPending ? t`Starting materialization…` : t`Run reviewed import`}</button>
        <ErrorText error={run.error} field="target_identity" />
      </div>
    ) : null}
    </>
  );
}

function VerificationReportView({ report, loading, error }: { report?: VerificationReport; loading: boolean; error: unknown }) {
  return (
    <section className="mt-3 rounded-md border border-line bg-accent-soft p-3" aria-label={t`Import verification report`}>
      <h4 className="title-section">{t`Verification report`}</h4>
      {loading ? <p className="mt-2 text-sm text-muted">{t`Loading the persisted verification report…`}</p> : null}
      <ErrorText error={error} />
      {report ? <>
        <p className="mt-2 text-sm text-ink">{t`Target makerspace ${report.target_makerspace_id} · ${report.identities_linked} linked · ${report.identities_created} walk-ins · ${report.external_references_created} external references`}</p>
        <div className="mt-2 grid gap-2 @2xl:grid-cols-3">
          {(["imported", "resolved", "dropped"] as const).map((key) => <div className="rounded border border-line bg-bg p-2" key={key}><p className="eyebrow">{key}</p><pre className="mt-1 overflow-auto text-xs text-muted">{JSON.stringify(report[key], null, 2)}</pre></div>)}
        </div>
      </> : null}
    </section>
  );
}

function importRunning(job: ImportJob) {
  return job.status === "pending" || job.status === "materializing" || job.status === "finalizing";
}
