import { useState } from "react";
import { Wallet } from "lucide-react";
import { DetailLayout } from "../../../components/layouts";
import { ConfirmDialog } from "../../../components/ui/ConfirmDialog";
import { reimbursementPath, useApplicantCommand, useReimbursement } from "./api";
import { commandError } from "../stagedForms/privateQueries";
import { useNow } from "../stagedForms/useNow";
import type { ReimbursementScope } from "./types";

export function Reimbursements({ scope, onRequest, onClaim, onAppeal, onPayout }: { scope: ReimbursementScope;
  onRequest: () => void; onClaim: () => void; onAppeal: () => void; onPayout: (id: string) => void }) {
  const query = useReimbursement(scope);
  const command = useApplicantCommand(scope);
  const [confirm, setConfirm] = useState<"award/accept" | "award/decline" | "request/withdraw" | null>(null);
  const now = useNow();
  const row = query.data;
  const allowed = (action: string) => row?.allowed_actions.includes(action);
  return <DetailLayout title="Travel support" state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "Travel support could not be loaded.", onRetry: () => void query.refetch() }} main={<div className="grid gap-5">
    <Wallet className="text-accent" size={28} aria-hidden="true" />
    {!row?.available ? <p>Travel support is unavailable for this event.</p> : <>
      <p>Support requests, award acceptance and expense claims each need your confirmation.</p>
      <ul className="list-disc pl-5">{row.programme?.policy.map(rule => <li key={rule}>{rule}</li>)}</ul>
      <section className="grid gap-3 rounded-2xl border border-line bg-panel p-5"><h2 className="title-section">Your request</h2>
        <p>{row.request ? `${row.request.state.replace(/_/g, " ")} · ${row.request.estimated_total_minor} minor units (${row.request.currency})` : "No support request submitted."}</p>
        {row.request?.reason ? <p>{row.request.reason}</p> : null}
        {allowed("request_draft") ? <button type="button" className="desk-button" disabled={command.isPending} onClick={() => command.mutate({
          path: reimbursementPath(scope), body: { expected_version: row.request?.version ?? 0 },
        }, { onSuccess: onRequest })}>Start support request</button> : null}
        {allowed("request_submit") ? <button type="button" className="desk-button" onClick={onRequest}>Prepare support request</button> : null}
        {allowed("request_withdraw") ? <button type="button" className="desk-button-danger-outline" onClick={() => setConfirm("request/withdraw")}>Withdraw request</button> : null}</section>
      {row.award ? <section className="grid gap-3 rounded-2xl border border-line bg-panel p-5"><h2 className="title-section">Your award</h2>
        <p>{row.award.state} · up to {row.award.amount_minor} minor units ({row.award.currency})</p><p>{row.award.note}</p>
        <ul className="list-disc pl-5">{row.award.rules.map(rule => <li key={rule}>{rule}</li>)}</ul>
        <p>Respond by <time dateTime={row.award.accept_by}>{new Date(row.award.accept_by).toLocaleString()}</time>. Reimbursement remains subject to eligible expenses and approval.</p>
        {now >= Date.parse(row.award.accept_by) && row.award.state === "offered" ? <p role="status">This offer deadline has passed.</p> : <div className="flex flex-wrap gap-3">
          {allowed("award_accept") ? <button type="button" className="desk-button-primary" onClick={() => setConfirm("award/accept")}>Accept award</button> : null}
          {allowed("award_decline") ? <button type="button" className="desk-button" onClick={() => setConfirm("award/decline")}>Decline award</button> : null}</div>}</section> : null}
      <section className="grid gap-3 rounded-2xl border border-line bg-panel p-5"><h2 className="title-section">Your expense claim</h2>
        <p>{row.claim?.state.replace(/_/g, " ") ?? "No claim yet."}</p>{row.claim?.reason ? <p>{row.claim.reason}</p> : null}
        {row.claim ? <p>Due {new Date(row.claim.info_due_at ?? row.claim.due_at).toLocaleString()}</p> : null}
        {allowed("claim_edit") || row.claim ? <button type="button" className="desk-button" onClick={onClaim}>Open expense claim</button> : null}
        {allowed("claim_appeal") ? <button type="button" className="desk-button" onClick={onAppeal}>Appeal decision</button> : null}
        {row.claim?.obligation_id ? <button type="button" className="desk-button" onClick={() => onPayout(row.claim!.obligation_id!)}>Payee details and payment history</button> : null}</section>
    </>}
    {command.error ? <p role="alert">{commandError(command.error)}</p> : null}
    <ConfirmDialog open={Boolean(confirm)} title={confirm === "award/accept" ? "Accept this award?" : confirm === "award/decline" ? "Decline this award?" : "Withdraw your request?"}
      message={confirm === "award/accept" ? "You accept the displayed cap and rules. Your event participation stays subject to its own confirmation." : "This releases any unaccepted offer. Your submitted history is retained."}
      pending={command.isPending} onCancel={() => setConfirm(null)} onConfirm={() => {
        if (!confirm || !row) return;
        command.mutate({ path: `${reimbursementPath(scope)}${confirm}/`, body: confirm.startsWith("award/") && row.award
          ? { expected_version: row.award.version, award_revision: row.award.award_revision } : { expected_version: row.request?.version ?? 0 } }, { onSuccess: () => setConfirm(null) });
      }} />
  </div>} />;
}
