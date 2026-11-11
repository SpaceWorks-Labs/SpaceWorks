import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import type { MembershipRequest } from "../../generated/api";
import { ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { CustomAnswersView } from "../forms/CustomAnswersView";
import type { AdmissionRequest, AdmissionVouch } from "../members/membershipAdmissionApi";
import { admissionStateLabel } from "../members/membershipLabels";
import { PaymentReconcileActions, type PaymentSummary } from "./PaymentReconcileActions";
import { RequestChangesDialog } from "./membershipLifecycle/RequestChangesDialog";

export type ReviewMembershipRequest = Omit<MembershipRequest, "state"> & AdmissionRequest;

export function MembershipVouchers({ vouches }: { vouches?: AdmissionVouch[] }) {
  return vouches?.length ? <div className="mt-3"><h4 className="text-sm font-semibold text-ink">{t`Vouchers`}</h4><ul className="text-sm text-muted">{vouches.map((vouch) => <li key={`${vouch.voucher_id}:${vouch.created_at}`}>{t`${vouch.voucher_name} · recorded ${new Date(vouch.created_at).toLocaleDateString(formatLocale())} · expires ${new Date(vouch.expires_at).toLocaleDateString(formatLocale())}`}</li>)}</ul></div> : null;
}

export function MembershipAdmissionReview({ row, makerspaceId, manageable, canViewFinance, canRecordPayment, canWaive, approvePending, declinePending, selectedRole, onApprove, onDecline, askChanges = false, onChanged }: {
  row: ReviewMembershipRequest; makerspaceId: number; manageable: boolean;
  canViewFinance: boolean; canRecordPayment: boolean; canWaive: boolean;
  approvePending: boolean; declinePending: boolean; selectedRole: number | null;
  onApprove: () => void; onDecline: () => void;
  /** Parity O-B2: `membership.ask_changes` is on, so a pending application can be sent back once. */
  askChanges?: boolean; onChanged?: () => void;
}) {
  const [asking, setAsking] = useState(false);
  const reviewable = ["requested", "invited", "awaiting_vouches"].includes(row.state);
  const cancelable = reviewable || row.state === "awaiting_payment" || row.state === "changes_requested";
  const canAsk = askChanges && row.kind === "request" && Boolean(row.user) && ["requested", "awaiting_vouches"].includes(row.state) && !row.changes_rounds;
  const name = row.user?.username ?? row.invite_email ?? "Membership request";
  return <article className="grid gap-3">
    <ListRow title={name} identity={{ kind: "avatar", name, seed: String(row.id) }}
      meta={<>{row.kind === "invite" ? t`Invitation` : t`Membership application`}{row.expires_at ? <> {t` · Expires `}<RelativeTime date={row.expires_at} /></> : null}</>}
      right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={admissionStateLabel(row.state)} tone={reviewable ? "warn" : row.state === "active" ? "success" : "neutral"} />
      {manageable && cancelable ? <div className="flex flex-wrap gap-2">
        {reviewable && (row.state !== "invited" || row.user) ? <button className="desk-button-primary" disabled={!selectedRole || approvePending} onClick={onApprove}>{t`Approve`}</button> : null}
        {canAsk ? <button className="desk-button" type="button" onClick={() => setAsking(true)}>{t`Ask for changes`}</button> : null}
        <button className="desk-button" disabled={declinePending} onClick={onDecline}>{row.state === "invited" ? t`Cancel invitation` : row.state === "awaiting_payment" ? t`Cancel application` : t`Decline`}</button>
      </div> : null}</div>} />
    {row.application_answers?.answers.length ? <details><summary className="cursor-pointer text-sm font-semibold text-ink">{t`Application answers`}</summary><div className="mt-3"><CustomAnswersView snapshot={row.application_answers} /></div></details> : null}
    {row.changes_note ? <p className="text-sm text-muted">{row.state === "changes_requested"
      ? t`Sent back for changes. Waiting for the applicant to edit and resubmit. Your note: “${row.changes_note}”`
      : t`Resubmitted after changes. Your note was: “${row.changes_note}”`}</p> : null}
    <MembershipVouchers vouches={row.vouches} />
    {asking ? <RequestChangesDialog makerspaceId={makerspaceId} requestId={row.id} applicant={name} onClose={() => setAsking(false)} onDone={() => onChanged?.()} /> : null}
    {row.state === "awaiting_payment" ? <p className="text-sm text-muted">{t`Approved; activation waits for the admission charge to be settled.`}</p> : null}
    {canViewFinance && row.admission_payment ? <PaymentReconcileActions makerspaceId={makerspaceId} payment={row.admission_payment as PaymentSummary} canRecordPayment={canRecordPayment} canWaive={canWaive} invalidateKeys={[["members", makerspaceId], ["member"]]} /> : null}
  </article>;
}
