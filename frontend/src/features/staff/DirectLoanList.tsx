import { t } from "@lingui/core/macro";
import { useContext, useState } from "react";

import { staffRequest } from "../../lib/api";
import { evidenceErrorText } from "./evidenceUi";
import { ListRow, OverflowMenu, RelativeTime, StatusPill } from "../../components/ui";
import { requestStatusLabel } from "../../components/ui/StatusStepper";
import { LoanChargesDisclosure } from "./loanCharges/LoanChargesPanel";
import { LoanContextPanel } from "./loanContext/LoanContextPanel";
import { LoanRepairsPanel } from "./loanRepairs/LoanRepairsPanel";
import { StaffListContext } from "./StaffListContext";
import { capabilityOn } from "../../lib/features";

export type DirectLoan = {
  has_kit_checklist?: boolean;
  id: number;
  request_id?: number;
  public_token: string;
  status: string;
  target_label: string;
  container_label?: string | null;
  due_at: string | null;
  issued_by: { username: string; role: string } | null;
  issue_evidence_id?: number | null;
  return_evidence_id?: number | null;
  return_notes?: string;
  return_scan_required?: boolean;
  items: { product_name: string; quantity: number }[];
  return_items?: DirectLoanReturnItem[];
};

export type DirectLoanReturnItem = {
  item_id: number;
  product_name: string;
  remaining_quantity: number;
  tracking_mode: string;
  assets: { asset_id: number; asset_tag: string }[];
};

export function DirectLoanList({
  loans,
  onReturn,
  makerspaceId, modules, unavailable,
}: {
  loans: DirectLoan[];
  onReturn: (loan: DirectLoan) => void;
  makerspaceId?: number; modules?: string[]; unavailable?: string[];
}) {
  const [contextLoanId, setContextLoanId] = useState<number | null>(null);
  // A damaged direct-handout return goes to repairs from here, as a reviewed loan does from its detail.
  const { makerspace } = useContext(StaffListContext);
  const repairsOn = Boolean(makerspace && makerspace.id === makerspaceId && capabilityOn(makerspace, "inventory.repairs"));
  const [repairsLoanId, setRepairsLoanId] = useState<number | null>(null);
  // Same domains LoanContextPanel renders; no toggle that can only open an empty panel.
  const contextOn = ["events", "bookings"].some(key => modules?.includes(key) && !unavailable?.includes(key));
  const [evidenceError, setEvidenceError] = useState<{ loanId: number; message: string } | null>(null);
  const openEvidence = async (loanId: number, evidenceId: number) => {
    setEvidenceError(null);
    try {
      const res = await staffRequest<{ url: string }>(`/admin/evidence/${evidenceId}`);
      window.open(res.url, "_blank", "noopener");
    } catch (error) {
      setEvidenceError({
        loanId,
        message: evidenceErrorText(error),
      });
    }
  };
  return <div className="grid gap-3">{loans.map(loan => <div key={loan.id}><ListRow title={loan.target_label}
    identity={loan.due_at ? { kind: "date", date: loan.due_at } : { kind: "avatar", name: loan.target_label, seed: String(loan.id) }}
    meta={<span className="grid gap-2">
      <span className="flex flex-wrap items-center gap-2"><StatusPill label={loan.status === "checked_out" ? t`Lent` : loan.status === "returned" ? t`Returned` : requestStatusLabel(loan.status)} tone={loan.status === "returned" ? "success" : loan.status === "checked_out" ? "accent" : "neutral"} />
        {loan.due_at ? <span>{t`Due `}<RelativeTime date={loan.due_at} /></span> : null}
      </span>
      <span>{t`Handout #${loan.id} · ${loan.items.map(item => `${item.product_name} × ${item.quantity}`).join(", ")}`}{loan.container_label ? t` · In ${loan.container_label}` : ""}{loan.issued_by ? t` · by ${loan.issued_by.username}` : ""}</span>
      {loan.status !== "checked_out" && loan.return_notes ? <span className="break-words">{loan.return_notes}</span> : null}
      {evidenceError?.loanId === loan.id ? <span className="text-danger" role="alert">{evidenceError.message}</span> : null}
      {makerspaceId && loan.request_id ? <LoanChargesDisclosure makerspaceId={makerspaceId} requestId={loan.request_id} /> : null}
    </span>}
    right={<div className="flex flex-wrap items-center gap-2">
      {contextOn && makerspaceId && loan.request_id ? <button type="button" className="desk-button" aria-expanded={contextLoanId === loan.id} aria-controls={`loan-context-${loan.id}`} onClick={() => setContextLoanId(contextLoanId === loan.id ? null : loan.id)}>{t`Context`}</button> : null}
      {loan.status === "checked_out" ? <button className="desk-button" onClick={() => onReturn(loan)}>{t`Return`}</button> : null}
      <OverflowMenu label={t`More actions for handout ${loan.id}`} actions={[
        ...(loan.issue_evidence_id ? [{ label: t`View issue photo`, onClick: () => void openEvidence(loan.id, loan.issue_evidence_id as number) }] : []),
        ...(loan.status !== "checked_out" && loan.return_evidence_id ? [{ label: t`View return photo`, onClick: () => void openEvidence(loan.id, loan.return_evidence_id as number) }] : []),
        ...(repairsOn && loan.status === "returned" && loan.request_id ? [{ label: repairsLoanId === loan.id ? t`Hide repairs` : t`Repairs`, onClick: () => setRepairsLoanId(repairsLoanId === loan.id ? null : loan.id) }] : []),
      ]} />
    </div>} /><div id={`loan-context-${loan.id}`}>{contextOn && contextLoanId === loan.id && makerspaceId && loan.request_id ? <LoanContextPanel tenant={makerspaceId} request={loan.request_id} modules={modules} unavailable={unavailable} /> : null}</div>
    {repairsOn && repairsLoanId === loan.id && makerspaceId && loan.request_id ? <div className="mt-2"><LoanRepairsPanel loan={{ id: loan.request_id, status: loan.status, makerspace_id: makerspaceId }} showEmpty /></div> : null}</div>)}</div>;
}
