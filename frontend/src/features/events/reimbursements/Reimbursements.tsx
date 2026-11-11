import { formatDateTime } from "../../../lib/format";
import { formatMinorMoney } from "../../../lib/money";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Wallet } from "lucide-react";
import { DetailLayout } from "../../../components/layouts";
import { ConfirmDialog } from "../../../components/ui/ConfirmDialog";
import { reimbursementPath, useApplicantCommand, useReimbursement } from "./api";
import { commandError } from "../stagedForms/privateQueries";
import { useNow } from "../stagedForms/useNow";
import type { ReimbursementOverview, ReimbursementScope } from "./types";
import { latestDecision, reimbursementStateLabel, travelCategoryLabel } from "./labels";

type Confirm = "award/accept" | "award/decline" | "request/withdraw";

/** The rules a member sees before asking: categories, per-category caps, exclusions and the claim deadline. */
function policyLines(row: ReimbursementOverview) {
  const programme = row.programme; const currency = programme.currency ?? row.award?.currency ?? "";
  const lines: string[] = [];
  if (programme.allowed_categories?.length) lines.push(t`Eligible travel: ${programme.allowed_categories.map(travelCategoryLabel).join(", ")}.`);
  for (const [category, cap] of Object.entries(programme.category_limits ?? {})) {
    if (typeof cap === "number") lines.push(t`${travelCategoryLabel(category)}: up to ${formatMinorMoney(cap, currency)}.`);
  }
  if (programme.exclusions?.length) lines.push(t`Not covered: ${programme.exclusions.join(", ")}.`);
  if (programme.attendance_required) lines.push(t`You must check in at the venue to be reimbursed.`);
  if (programme.claim_due_at) lines.push(t`Expense claims are due by ${formatDateTime(programme.claim_due_at)}.`);
  return lines;
}

export function Reimbursements({ scope, onRequest, onClaim, onAppeal, onPayout }: { scope: ReimbursementScope;
  onRequest: () => void; onClaim: () => void; onAppeal: () => void; onPayout: (id: string) => void }) {
  const query = useReimbursement(scope);
  const command = useApplicantCommand(scope);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const now = useNow();
  const row = query.data;
  const allowed = (action: string) => Boolean(row?.allowed_actions.includes(action));
  const claim = row?.claim ?? null;
  const decision = latestDecision(claim);
  return <DetailLayout title={t`Travel support`} state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: t`Travel support could not be loaded.`, onRetry: () => void query.refetch() }} main={<div className="grid gap-5">
    <Wallet className="text-accent-ink" size={28} aria-hidden="true" />
    {!row?.available && !row?.request ? <p>{t`Travel support is unavailable for this event.`}</p> : row ? <>
      <p>{t`Support requests, award acceptance and expense claims each need your confirmation.`}</p>
      <ul className="list-disc pl-5">{policyLines(row).map(rule => <li key={rule}>{rule}</li>)}</ul>
      <section className="grid gap-3 rounded-2xl border border-line bg-panel p-5"><h2 className="title-section">{t`Your request`}</h2>
        <p>{row.request && row.request.state !== "draft" ? t`${reimbursementStateLabel(row.request.state)} · estimated ${formatMinorMoney(row.request.estimated_total_minor, row.request.currency)}` : t`No support request submitted.`}</p>
        {row.request?.reason ? <p>{row.request.reason}</p> : null}
        {allowed("create_request") || allowed("submit_request") ? <button type="button" className="desk-button" disabled={command.isPending} onClick={() => {
          if (row.request) onRequest();
          else command.mutate({ path: reimbursementPath(scope), body: { expected_version: 0 } }, { onSuccess: onRequest });
        }}>{row.request ? t`Continue support request` : t`Start support request`}</button> : null}
        {allowed("withdraw_request") ? <button type="button" className="desk-button-danger-outline" onClick={() => setConfirm("request/withdraw")}>{t`Withdraw request`}</button> : null}</section>
      {row.award ? <section className="grid gap-3 rounded-2xl border border-line bg-panel p-5"><h2 className="title-section">{t`Your award`}</h2>
        <p>{t`${reimbursementStateLabel(row.award.state)} · up to ${formatMinorMoney(row.award.amount_minor, row.award.currency)}`}</p>
        {row.award.reason_code === "direct_booking" ? <p>{t`The organisers booked your travel directly, so there is nothing to claim.`}</p> : null}
        {row.award.state === "offered" ? <p>{t`Respond by ${formatDateTime(row.award.accept_by)}. Reimbursement remains subject to eligible expenses and approval.`}</p> : null}
        {row.award.state === "offered" && now >= Date.parse(row.award.accept_by) ? <p role="status">{t`This offer deadline has passed.`}</p> : <div className="flex flex-wrap gap-3">
          {allowed("accept_award") ? <button type="button" className="desk-button-primary" onClick={() => setConfirm("award/accept")}>{t`Accept award`}</button> : null}
          {allowed("decline_award") ? <button type="button" className="desk-button" onClick={() => setConfirm("award/decline")}>{t`Decline award`}</button> : null}</div>}</section> : null}
      {claim || allowed("create_claim") ? <section className="grid gap-3 rounded-2xl border border-line bg-panel p-5"><h2 className="title-section">{t`Your expense claim`}</h2>
        <p>{claim ? reimbursementStateLabel(claim.display_state) : t`No claim yet.`}</p>{decision?.reason ? <p>{decision.reason}</p> : null}
        {claim ? <p>{t`Due ${formatDateTime(claim.info_due_at ?? claim.effective_due_at)}`}</p> : null}
        {claim?.payout ? <p>{t`Approved ${formatMinorMoney(claim.payout.approved_minor, claim.payout.currency)} · paid ${formatMinorMoney(claim.payout.effective_paid_minor, claim.payout.currency)}`}</p> : null}
        <button type="button" className="desk-button" onClick={onClaim}>{claim ? t`Open expense claim` : t`Start expense claim`}</button>
        {claim?.allowed_actions.includes("appeal") ? <button type="button" className="desk-button" onClick={onAppeal}>{t`Appeal decision`}</button> : null}
        {claim?.payout ? <button type="button" className="desk-button" onClick={() => onPayout(claim.payout!.id)}>{t`Payee details and payment history`}</button> : null}</section> : null}
    </> : null}
    {command.error ? <p role="alert">{commandError(command.error)}</p> : null}
    <ConfirmDialog open={Boolean(confirm)} title={confirm === "award/accept" ? t`Accept this award?` : confirm === "award/decline" ? t`Decline this award?` : t`Withdraw your request?`}
      message={confirm === "award/accept" ? t`You accept the displayed cap and rules. Your event participation stays subject to its own confirmation.` : t`This releases any unaccepted offer. Your submitted history is retained.`}
      pending={command.isPending} onCancel={() => setConfirm(null)} onConfirm={() => {
        if (!confirm || !row) return;
        command.mutate({ path: `${reimbursementPath(scope)}${confirm}/`, body: confirm.startsWith("award/") && row.award
          ? { expected_version: row.award.version, award_revision: row.award.award_revision } : { expected_version: row.request?.version ?? 0 } }, { onSuccess: () => setConfirm(null) });
      }} />
  </div>} />;
}
