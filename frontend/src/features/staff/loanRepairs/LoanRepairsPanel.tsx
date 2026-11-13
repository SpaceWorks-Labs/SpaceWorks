import { plural, t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Wrench } from "lucide-react";
import { useContext, useState } from "react";

import { StatusPill } from "../../../components/ui";
import { capabilityOn } from "../../../lib/features";
import { StaffListContext } from "../StaffListContext";
import { opsStatusLabel } from "../opsPresentation";
import { formatMoney } from "../paymentsApi";
import {
  getLoanRepairs, handOffToRepairs, isHiddenError, loanCanHaveRepairs, loanRepairsKey,
  type LoanRepairIssue, type LoanRepairLine,
} from "./loanRepairsApi";
import { LogoLoader } from "../../../components/LogoLoader";

type LoanLike = { id: number; status: string; makerspace_id?: number };

/** A returned loan's damaged lines: send one to repairs, then follow its parts and cost.
 * `showEmpty` is for an on-demand opening (a handout row's Repairs action): say so when there is nothing. */
export function LoanRepairsPanel({ loan, showEmpty = false }: { loan: LoanLike; showEmpty?: boolean }) {
  const { makerspace } = useContext(StaffListContext);
  if (!loan.makerspace_id || !loanCanHaveRepairs(loan.status)) return null;
  // `inventory.repairs` off answers 404; with the space in context, do not ask at all.
  if (makerspace?.id === loan.makerspace_id && !capabilityOn(makerspace, "inventory.repairs")) return null;
  return <LoanRepairsSection makerspaceId={loan.makerspace_id} requestId={loan.id} showEmpty={showEmpty} />;
}

function lineTitle(line: LoanRepairLine) {
  const unit = line.asset_tag ? ` (${line.asset_tag})` : "";
  return t`${line.product_name}${unit} · ${line.quantity} damaged`;
}

function RepairDetail({ issue }: { issue: LoanRepairIssue }) {
  const cost = issue.payout_amount ? t`Paid ${formatMoney(issue.payout_amount, issue.payout_currency)}`
    : issue.quote_amount ? t`Quoted ${formatMoney(issue.quote_amount, issue.quote_currency)}` : "";
  return <div className="grid gap-1 text-sm">
    <span className="flex flex-wrap items-center gap-2 text-ink">{t`Repair #${issue.id}`}
      <StatusPill label={opsStatusLabel(issue.state)} tone={issue.state === "fixed" || issue.state === "closed" ? "success" : "info"} />
      {issue.work_order ? <span className="text-muted">{t`Work order #${issue.work_order.id}: ${opsStatusLabel(issue.work_order.status)}`}</span> : null}
    </span>
    {cost ? <span className="tabular-nums text-ink">{cost}</span> : null}
    {issue.parts.length ? <ul aria-label={t`Parts`} className="grid gap-1 text-muted">{issue.parts.map(part =>
      <li key={part.id}>{part.kind === "used" ? t`Used ${part.quantity} x ${part.name}` : t`Needs ${part.quantity} x ${part.name}`}</li>)}</ul> : null}
    {issue.to_buy_items.length ? <ul aria-label={t`To buy`} className="grid gap-1 text-muted">{issue.to_buy_items.map(item => {
      const unitCost = item.actual_unit_cost ?? item.estimated_unit_cost;
      const status = opsStatusLabel(item.status);
      const receipts = item.receipts.length;
      return <li key={item.id}>{t`To buy: ${item.quantity} x ${item.name} · ${status}`}
        {unitCost ? t` · ${unitCost} each` : ""}{receipts ? plural(receipts, { one: " · # receipt", other: " · # receipts" }) : ""}</li>;
    })}</ul> : null}
  </div>;
}

function LoanRepairsSection({ makerspaceId, requestId, showEmpty }: { makerspaceId: number; requestId: number; showEmpty: boolean }) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: loanRepairsKey(makerspaceId, requestId),
    queryFn: () => getLoanRepairs(makerspaceId, requestId),
    retry: (count, error) => !isHiddenError(error) && count < 2,
  });
  const [notes, setNotes] = useState<Record<number, string>>({});
  const send = useMutation({
    mutationFn: (accountabilityId: number) => handOffToRepairs(makerspaceId, requestId, accountabilityId, notes[accountabilityId] ?? ""),
    onSuccess: (_result, accountabilityId) => setNotes(current => { const next = { ...current }; delete next[accountabilityId]; return next; }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: loanRepairsKey(makerspaceId, requestId) }),
  });
  if (query.isLoading) return showEmpty ? <LogoLoader label={t`Loading repairs…`} size={48} className="min-h-16 py-3" /> : null;
  if (query.error && isHiddenError(query.error)) return showEmpty ? <p className="text-sm text-muted">{t`Repairs are not available to you for this loan.`}</p> : null;
  if (query.error) return <p className="text-sm text-danger" role="alert">{t`Couldn't load this loan's repairs.`}</p>;
  const lines = query.data?.lines ?? [];
  if (!lines.length) return showEmpty ? <p className="text-sm text-muted">{t`Nothing on this loan came back damaged.`}</p> : null;
  return <section aria-label={t`Repairs`} className="grid gap-3">
    <h2 className="title-panel flex items-center gap-2"><Wrench aria-hidden="true" size={18} />{t`Repairs`}</h2>
    <ul className="grid gap-2">{lines.map(line => <li key={line.accountability_id} className="grid gap-2 rounded-xl border border-line p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="min-w-0 break-words text-ink">{lineTitle(line)}{line.remark ? <span className="text-muted"> · {line.remark}</span> : null}</span>
        {/* A reviewer sees only that a repair is open; detail stays with the item managers (221c). */}
        {line.issue ? null : line.handed_off ? <StatusPill tone="info" label={t`In repairs`} /> : <button className="desk-button" type="button" disabled={send.isPending}
          aria-label={t`Send ${lineTitle(line)} to repairs`} onClick={() => send.mutate(line.accountability_id)}>{t`Send to repairs`}</button>}
      </div>
      {!line.issue && !line.handed_off ? <label className="grid gap-1 text-sm text-muted">{t`Note for repairs (optional)`}
        <textarea className="desk-input" rows={2} maxLength={2000} disabled={send.isPending} value={notes[line.accountability_id] ?? ""}
          onChange={event => setNotes(current => ({ ...current, [line.accountability_id]: event.target.value }))} /></label> : null}
      {line.issue ? <RepairDetail issue={line.issue} /> : null}
    </li>)}</ul>
    {send.error ? <p className="text-sm text-danger" role="alert">{t`That did not work. Try again.`}</p> : null}
  </section>;
}
