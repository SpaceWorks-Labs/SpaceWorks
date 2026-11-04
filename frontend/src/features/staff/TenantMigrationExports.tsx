import { useState } from "react";
import { DangerZone } from "../../components/ui";
import { useMigrationConfirmation } from "./MigrationConfirmation";
import type { Query } from "@tanstack/react-query";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  archiveSource,
  createMigrationExport,
  getMigrationExport,
  issueMigrationDownload,
  listDisclosureApprovals,
  listMigrationExports,
  quiesceSource,
  recoverSource,
  tenantMigrationKeys,
  type MigrationExportJob,
  type Pairing,
  type ReceiptEnvelope,
} from "./tenantMigrationApi";
import { ErrorText, openDownload, parseReceipt, ReceiptOutput, StatusPill } from "./tenantMigrationUi";

export function TenantMigrationExports({
  makerspaceId,
  tenantName,
  closureDigest,
  pairings,
  active = true,
  phase = "export",
}: {
  makerspaceId: number;
  tenantName: string;
  closureDigest?: string;
  pairings: Pairing[];
  active?: boolean;
  phase?: "export" | "cutover";
}) {
  const client = useQueryClient();
  const [confirmCutover, confirmation] = useMigrationConfirmation();
  const [approvalId, setApprovalId] = useState("");
  const [recipient, setRecipient] = useState("");
  const [abortReceipts, setAbortReceipts] = useState<Record<string, string>>({});
  const approvals = useQuery({
    queryKey: tenantMigrationKeys.approvals(makerspaceId),
    queryFn: () => listDisclosureApprovals(makerspaceId),
  });
  const exportsQuery = useQuery({
    queryKey: tenantMigrationKeys.exports(makerspaceId),
    queryFn: () => listMigrationExports(makerspaceId),
  });
  const exportDetails = useQueries({
    queries: (exportsQuery.data ?? []).map((job) => ({
      queryKey: tenantMigrationKeys.export(makerspaceId, job.id),
      queryFn: () => getMigrationExport(makerspaceId, job.id),
      // `useQueries` with a computed array loses per-entry inference in Query v5,
      // so the callback argument is annotated rather than left implicitly `any`.
      refetchInterval: (query: Query) => exportRunning((query.state.data as MigrationExportJob | undefined) ?? job) ? 1500 : false,
    })),
  });
  const validApprovals = approvals.data?.filter(
    (item) => !item.revoked_at && item.closure_digest === closureDigest,
  ) ?? [];
  const selectedApproval = approvalId || validApprovals[0]?.id || "";
  const createExport = useMutation({
    mutationFn: () => createMigrationExport(makerspaceId, {
      approval_id: selectedApproval,
      target_age_recipient: recipient.trim(),
    }),
    onSuccess: () => client.invalidateQueries({ queryKey: tenantMigrationKeys.exports(makerspaceId) }),
  });
  const download = useMutation({
    mutationFn: (jobId: string) => issueMigrationDownload(makerspaceId, jobId),
    onSuccess: ({ url }) => openDownload(url),
  });
  const quiesce = useMutation({
    mutationFn: (jobId: string) => quiesceSource(makerspaceId, jobId),
    onSuccess: (_data, jobId) => {
      client.invalidateQueries({ queryKey: tenantMigrationKeys.exports(makerspaceId) });
      client.invalidateQueries({ queryKey: tenantMigrationKeys.export(makerspaceId, jobId) });
    },
  });
  const archive = useMutation({
    mutationFn: (pairingId: string) => archiveSource(makerspaceId, pairingId),
    onSuccess: () => client.invalidateQueries({ queryKey: ["staff", "makerspaces"] }),
  });
  const recover = useMutation({
    mutationFn: ({ pairingId, receipt }: { pairingId: string; receipt: ReceiptEnvelope }) =>
      recoverSource(makerspaceId, pairingId, { receipt }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["staff", "makerspaces"] }),
  });

  if (!active) return null;
  return (
    <section aria-labelledby="migration-export-title" className="min-w-0">
      <p className="eyebrow">Source deployment</p>
      <h3 className="title-section" id="migration-export-title">Encrypted migration exports</h3>
      <p className="mt-2 text-sm text-ink">
        The target age recipient encrypts the portable archive for one target deployment. Quiescing
        freezes writes to {tenantName}. Archiving the source is a one-way cutover action from this screen.
      </p>
      <p className="mt-2 text-sm font-semibold text-danger">
        The source tenant is archived, not deleted, at cutover. Archives are outside the purge guarantee.
      </p>

      {phase === "export" ? <>
      <div className="mt-4 grid gap-3 @xl:grid-cols-2">
        <label className="text-sm text-ink">
          Approved closure
          <select className="desk-input mt-1 w-full" value={selectedApproval} onChange={(event) => setApprovalId(event.target.value)}>
            {validApprovals.length === 0 ? <option value="">Approve the current closure first</option> : null}
            {validApprovals.map((approval) => <option key={approval.id} value={approval.id}>{approval.approved_count}/{approval.identity_count} disclosed · {approval.id}</option>)}
          </select>
        </label>
        <label className="text-sm text-ink">
          Target age recipient
          <input className="desk-input mt-1 w-full code-text" value={recipient} onChange={(event) => setRecipient(event.target.value)} placeholder="age1…" />
        </label>
      </div>
      <button className="desk-button-primary mt-3" type="button" disabled={!selectedApproval || !recipient.trim() || createExport.isPending} onClick={() => createExport.mutate()}>
        {createExport.isPending ? "Requesting encrypted export…" : "Create encrypted migration export"}
      </button>
      <ErrorText error={createExport.error} field="target_age_recipient" />
      </> : null}

      {exportsQuery.isLoading ? <p className="mt-4 text-sm text-muted">Loading migration exports…</p> : null}
      <ErrorText error={exportsQuery.error} />
      <div className="mt-4 grid gap-3">
        {(exportsQuery.data ?? []).map((listedJob, index) => {
          const job = exportDetails[index]?.data ?? listedJob;
          const pairing = pairings.find((item) => item.archive_digest === job.archive_digest);
          const abortReceiptText = pairing ? abortReceipts[pairing.id] ?? "" : "";
          const abortReceipt = parseReceipt(abortReceiptText);
          return (
            <article className="rounded-md border border-line bg-surface p-3" key={job.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-ink">Export {job.id}</p>
                  <p className="mt-1 break-all code-text text-xs text-muted">Archive digest: {job.archive_digest || "Pending"}</p>
                </div>
                <StatusPill tone={job.status === "failed" ? "danger" : job.status === "available" ? "success" : "warn"}>{(job.status ?? "pending").toUpperCase()}</StatusPill>
              </div>
              {job.failure_detail ? <p className="mt-2 text-sm text-danger" role="alert">{job.failure_detail}</p> : null}
              <ErrorText error={exportDetails[index]?.error} />
              <p className="mt-2 text-xs text-muted">{job.source_retention_notice}</p>
              {quiesce.isSuccess && quiesce.variables === job.id ? <p className="mt-2 text-sm font-semibold text-danger" role="status">Source writes are frozen for this cutover.</p> : null}
              {job.status === "available" ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className="desk-button" type="button" disabled={download.isPending} onClick={() => download.mutate(job.id)}>Download one-use archive</button>
                  {phase === "cutover" ? <div className="w-full">
                    <DangerZone title={`Quiesce ${tenantName}`} consequence="Freeze source writes before cutover."
                      action={{ label: `Quiesce ${tenantName}`, pending: quiesce.isPending, pendingLabel: "Freezing writes…",
                        onClick: () => confirmCutover({ title: `Quiesce ${tenantName}`, name: tenantName, consequence: "This freezes source writes before cutover.", onConfirm: () => quiesce.mutate(job.id) }) }} />
                    {pairing ? <DangerZone title={`Archive source ${tenantName}`} consequence="This source cutover cannot be undone from this screen."
                      action={{ label: `Archive source ${tenantName}`, pending: archive.isPending, pendingLabel: "Archiving source…",
                        onClick: () => confirmCutover({ title: `Archive source ${tenantName}`, name: tenantName, consequence: "This source cutover cannot be undone from this screen.", onConfirm: () => archive.mutate(pairing.id) }) }} /> : null}
                  </div> : null}                </div>
              ) : null}
              {pairing && phase === "cutover" ? (
                <div className="mt-3 rounded-md border border-line p-3">
                  <p className="text-xs text-muted">Pinned pairing <span className="tabular-nums">{pairing.id}</span></p>
                  <label className="mt-2 block text-sm text-ink">
                    Target ABORTED receipt (only for recovery after target abort)
                    <textarea className="desk-input mt-1 min-h-24 w-full code-text text-base md:text-xs" value={abortReceiptText} onChange={(event) => setAbortReceipts((current) => ({ ...current, [pairing.id]: event.target.value }))} />
                  </label>
                  <DangerZone title={`Recover source ${tenantName}`} consequence="Recover only after the target is ABORTED and its signed receipt is available."
                    action={{ label: `Recover source ${tenantName}`, disabled: !abortReceipt, disabledReason: "Paste a valid signed target ABORTED receipt first.", pending: recover.isPending, pendingLabel: "Recovering source…",
                      onClick: () => { if (abortReceipt) confirmCutover({ title: `Recover source ${tenantName}`, name: tenantName, consequence: "Recover only after the target is ABORTED.", onConfirm: () => recover.mutate({ pairingId: pairing.id, receipt: abortReceipt }) }); } }} />
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
      <ErrorText error={download.error ?? quiesce.error ?? archive.error ?? recover.error} field="receipt" />
      <ReceiptOutput label="Source cutover receipt — transfer to target" receipt={archive.data?.receipt} />
      {recover.data ? <p className="mt-3 text-sm text-success-ink" role="status">{recover.data.message}</p> : null}
      {confirmation}
    </section>
  );
}

function exportRunning(job: MigrationExportJob) {
  return job.status === "pending" || job.status === "running";
}
