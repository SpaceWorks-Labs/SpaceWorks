import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../../lib/api";
import { memberPayoutKey, memberPayoutPath, usePayeeContext } from "./api";
import { collectedPayee, permits } from "./types";
import type { Payee, PayoutDetail } from "./types";

type Upload = { method: string; url: string; fields: Record<string, string>; expires_at: string };
type Created = { asset_id: number; generation: number; state: string; upload?: Upload };
type FileStatus = { asset_id: number; generation: number; version: number; state: string; filename: string;
  bytes: number; scan_status: string; error_code: string };
/** `GET payee-files/`: the owner's own files for the current payee details, metadata only. */
type Listed = { id: number; filename: string; size: number; uploaded_at: string; status: string };
type Shown = Pick<FileStatus, "asset_id" | "filename" | "state">;

const TYPES = ["application/pdf", "image/jpeg", "image/png"];
const MAX_BYTES = 10 * 1024 * 1024;
const command = (body: Record<string, unknown>) => {
  const operation = crypto.randomUUID();
  return { method: "POST", cache: "no-store" as const, headers: { "Idempotency-Key": operation },
    body: JSON.stringify({ ...body, operation_id: operation }) };
};
const fileStateLabel = (state: string) => ({ initiated: t`Uploading`, uploaded: t`Checking`, validating: t`Checking`,
  ready: t`Ready for finance review`, attached: t`Attached to your routing`, failed: t`Could not be accepted`, expired: t`Removed` } as Record<string, string>)[state] ?? state.replace(/_/g, " ");

/** Shown only while routing is requested and the chosen, still unverified method needs a document. */
export function PayeeFilesSection({ actorId, payout }: { actorId: number; payout: PayoutDetail }) {
  const payee = collectedPayee(payout.payee);
  if (!payee || payee.verified || !permits(payout, "submit_payee")) return null;
  return <RoutingDocumentGate actorId={actorId} payout={payout} />;
}

function RoutingDocumentGate({ actorId, payout }: { actorId: number; payout: PayoutDetail }) {
  const context = usePayeeContext(actorId, payout.id);
  const payee = collectedPayee(context.data?.payee);
  const methods = (context.data as { routing_document_methods?: unknown[][] } | undefined)?.routing_document_methods ?? [];
  const needed = payee && methods.some(pair => pair[0] === payee.country && pair[1] === payee.method);
  if (!payee || payee.verified || !needed || !permits(context.data, "submit_payee")) return null;
  return <PayeeFiles key={`${payee.id}:${payee.version}`} actorId={actorId} payout={payout} payee={payee} />;
}

/**
 * The owner's routing document for one reimbursement (`member/event-payouts/{id}/payee-files/…`).
 * Every route is owner-only on the server; the list starts from the owner's files already uploaded
 * for these payee details and never reads anyone else's. Bytes go straight to the presigned staging upload.
 */
export function PayeeFiles({ actorId, payout, payee }: { actorId: number; payout: PayoutDetail; payee: Payee }) {
  const client = useQueryClient();
  const base = `${memberPayoutPath(payout.id)}/payee-files/`;
  const [files, setFiles] = useState<Shown[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const version = async () => (await memberRequest<PayoutDetail>(`${memberPayoutPath(payout.id)}/`, { cache: "no-store" })).version;
  const status = (assetId: number) => memberRequest<FileStatus>(`${base}${assetId}/`, { cache: "no-store" });
  const keep = (row: Shown) => setFiles(rows => [...rows.filter(item => item.asset_id !== row.asset_id), row]);
  useEffect(() => {
    let live = true;
    memberRequest<Listed[]>(base, { cache: "no-store" }).then(rows => {
      if (!live) return;
      const listed = rows.map(row => ({ asset_id: row.id, filename: row.filename, state: row.status }));
      // A file added or refreshed while this was loading keeps its newer status.
      setFiles(current => [...listed.filter(row => !current.some(item => item.asset_id === row.asset_id)), ...current]);
    }, () => { if (live) setError(t`Your uploaded files could not be loaded. Refresh the page to try again.`); });
    return () => { live = false; };
  }, [base]);
  const run = async (work: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await work(); } catch (reason) { setError(reason instanceof Error ? reason.message : t`The file was not changed. Try again.`); }
    finally { setBusy(false); void client.invalidateQueries({ queryKey: memberPayoutKey(actorId) }); }
  };
  const add = (file: File) => run(async () => {
    if (!TYPES.includes(file.type) || file.size < 1 || file.size > MAX_BYTES) throw new Error(t`Choose a PDF, JPEG or PNG up to 10 MB.`);
    const created = await memberRequest<Created>(base, command({ expected_version: await version(), payee_revision_id: payee.id,
      expected_payee_version: payee.version, question_id: "routing_document", filename: file.name, bytes: file.size, mime: file.type }));
    try {
      if (created.upload) {
        const form = new FormData();
        Object.entries(created.upload.fields).forEach(([key, value]) => form.append(key, value));
        form.append("file", file);
        const response = await fetch(created.upload.url, { method: created.upload.method || "POST", body: form });
        if (!response.ok) throw new Error(t`The upload did not reach storage. Try again.`);
        const uploaded = await status(created.asset_id);
        await memberRequest(`${base}${created.asset_id}/complete/`, command({ expected_version: await version(),
          expected_asset_version: uploaded.version, generation: uploaded.generation }));
      }
    } finally {
      // Listed even after a failed upload, so the person can see it and remove it.
      keep(await status(created.asset_id));
    }
  });
  const refresh = (row: Shown) => run(async () => keep(await status(row.asset_id)));
  const remove = (row: Shown) => run(async () => {
    const current = await status(row.asset_id);
    await memberRequest(`${base}${row.asset_id}/`, { ...command({ expected_version: await version(),
      expected_asset_version: current.version, generation: current.generation }), method: "DELETE" });
    setFiles(rows => rows.filter(item => item.asset_id !== row.asset_id));
  });
  return <section className="grid gap-3 rounded-2xl border border-line bg-panel p-5" aria-label={t`Routing document`}>
    <h2 className="font-semibold">{t`Routing document`}</h2>
    <p className="text-sm text-muted">{t`This payment method needs a document that confirms your account, such as a bank letter. Only you and authorized finance staff can open it.`}</p>
    <label className="grid gap-1 text-sm">{t`Upload a routing document`}
      <input className="desk-input" type="file" accept={TYPES.join(",")} disabled={busy}
        onChange={event => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void add(file); }} /></label>
    {busy ? <p role="status" className="text-sm text-muted">{t`Working on your file…`}</p> : null}
    {files.length ? <ul className="grid gap-2">{files.map(row => <li key={row.asset_id} className="flex flex-wrap items-center gap-2 text-sm">
      <span className="min-w-0 flex-1 break-words">{row.filename} · {fileStateLabel(row.state)}</span>
      <button type="button" className="desk-button min-h-11" disabled={busy} onClick={() => void refresh(row)}>{t`Refresh status`}</button>
      {row.state !== "attached" ? <button type="button" className="desk-button-danger-outline min-h-11" disabled={busy}
        aria-label={t`Remove ${row.filename}`} onClick={() => void remove(row)}>{t`Remove`}</button> : null}
    </li>)}</ul> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
  </section>;
}
