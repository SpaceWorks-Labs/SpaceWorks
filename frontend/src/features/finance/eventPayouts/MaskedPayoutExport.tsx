import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { staffRequest, staffRequestBlob } from "../../../lib/api";
import { payoutPath, useCommandIdentity } from "./api";
import { money, scopeIdentity } from "./format";
import { usePrivateRequest } from "./usePrivateRequest";
import { permits } from "./types";
import type { FinanceScope, Preview } from "./types";

export function MaskedPayoutExport(props: { scope: FinanceScope; ids: string[]; allowed: boolean }) {
  return <ExportContent key={`${scopeIdentity(props.scope.actorId, props.scope.makerspaceId)}:${props.ids.join()}:${props.allowed}`} {...props} />;
}
function ExportContent({ scope, ids, allowed }: { scope: FinanceScope; ids: string[]; allowed: boolean }) {
  const identity = useCommandIdentity();
  const request = usePrivateRequest<Preview>(scopeIdentity(scope.actorId, scope.makerspaceId));
  const download = usePrivateRequest<boolean>(scopeIdentity(scope.actorId, scope.makerspaceId));
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  const batch = request.data;
  const expired = batch ? !Number.isFinite(Date.parse(batch.expires_at)) || now >= Date.parse(batch.expires_at) : false;
  if (!allowed) return null;
  return <section className="grid gap-3 rounded-2xl border border-line bg-panel p-5" aria-label="Masked payout CSV">
    <h2 className="font-semibold">Masked payout checklist</h2><p>Selected: {ids.length}. Preview and CSV contain masked routing only. Exporting never records a payout or sends money. Batches expire after 24 hours and are rechecked before download.</p>
    <button className="desk-button min-h-11" type="button" disabled={!ids.length || ids.length > 500 || request.pending}
      onClick={() => {
        download.clear();
        if (expired || batch && !batch.preview?.length) identity.clear();
        const data = { expected_version: 0, obligation_ids: [...ids].sort() };
        const operation = identity.forPayload(data);
        void request.run(signal => staffRequest<Preview>(`${payoutPath(scope)}/exports/`, {
          method: "POST", cache: "no-store", signal, headers: { "Idempotency-Key": operation },
          body: JSON.stringify({ ...data, operation_id: operation }),
        }));
      }}>Preview masked CSV</button>
    {request.failed ? <p role="alert">The batch could not be prepared. Reload selection, payee verification and current eligibility, then reauthenticate.</p> : null}
    {batch ? <><p>Batch {batch.id} · expires {batch.expires_at}</p>
      {batch.preview?.length ? <ul className="grid gap-2">{batch.preview.map(row => <li key={row.obligation_id} className="rounded-xl border border-line p-3">
        <span>{row.obligation_id} · {money(row.remaining_minor, row.currency)} · {row.masked_payee}</span>
      </li>)}</ul> : <p role="alert">This response has no preview. Create a new reviewed batch before downloading.</p>}
      {expired ? <p role="status">This batch expired. Prepare a new preview.</p> : null}
      <button className="desk-button min-h-11" type="button" disabled={expired || !batch.preview?.length || !permits(batch, "export") || download.pending}
        onClick={() => { void download.run(async signal => {
          let blob: Blob;
          try { blob = await staffRequestBlob(`${payoutPath(scope)}/exports/${encodeURIComponent(batch.id)}/download/`, { cache: "no-store", signal }); }
          catch { identity.clear(); throw new Error("batch_download_refused"); }
          if (signal.aborted || document.visibilityState !== "visible") return false;
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a"); link.href = url; link.download = `payout-checklist-${batch.id}.csv`;
          document.body.appendChild(link); link.click(); link.remove();
          window.setTimeout(() => URL.revokeObjectURL(url), 1000);
          return true;
        }); }}><Download aria-hidden="true" size={18} />Download masked CSV</button>
      {download.failed ? <p role="alert">Download refused. The batch may have expired or a selected obligation changed. Prepare a new preview.</p> : null}
      {download.data ? <p role="status">Masked checklist downloaded. No payout was recorded.</p> : null}
    </> : null}
  </section>;
}
