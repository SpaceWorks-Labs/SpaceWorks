import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { HandCoins, Receipt } from "lucide-react";

import { StatusPill } from "../../../components/ui";
import { formatMoney } from "../paymentsApi";
import { AccountabilityChargeForm, rowTitle } from "./AccountabilityChargeForm";
import {
  chargeStatus, getLoanCharges, isHiddenError, loanCanCarryCharges, loanChargesKey, loanChargesOn,
  type LoanCharge, type LoanCharges, type LoanFeeWaiver,
} from "./loanChargesApi";
import { RevokeWaiverDialog } from "./RevokeWaiverDialog";
import { WaiveFeesDialog } from "./WaiveFeesDialog";
import { WaiverHistory } from "./WaiverHistory";

type LoanLike = { id: number; status: string; makerspace_id?: number };

/** One loan's money: its charges, damage/lost decisions and fee waivers. Hidden before a loan can owe anything. */
export function LoanChargesPanel({ loan }: { loan: LoanLike }) {
  if (!loan.makerspace_id || !loanCanCarryCharges(loan.status)) return null;
  return <LoanChargesSection makerspaceId={loan.makerspace_id} requestId={loan.id} />;
}

export function useLoanCharges(makerspaceId: number, requestId: number) {
  return useQuery({
    queryKey: loanChargesKey(makerspaceId, requestId),
    queryFn: () => getLoanCharges(makerspaceId, requestId),
    retry: (count, error) => !isHiddenError(error) && count < 2,
  });
}

function ChargeLine({ charge }: { charge: LoanCharge }) {
  const [label, tone] = chargeStatus(charge.status);
  return <li className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line p-3 text-sm">
    <span className="min-w-0 break-words text-ink">{charge.label}</span>
    <span className="flex items-center gap-2">
      <span className="tabular-nums font-semibold text-ink">{formatMoney(charge.amount, charge.currency)}</span>
      <StatusPill label={label} tone={tone} />
    </span>
  </li>;
}

/** What a save that raised nothing means: staff chose no charge, or a waiver already covers it. */
export function freeNotice(reason: string | null) {
  if (reason === "waived") return "Saved. A fee waiver on this loan brings it to zero, so nothing was charged.";
  if (reason === "no_charge") return "No charge (decided).";
  return "";
}

/** A "Charges" disclosure for lists without a detail view; it fetches only once opened. */
export function LoanChargesDisclosure({ makerspaceId, requestId }: { makerspaceId: number; requestId: number }) {
  const [open, setOpen] = useState(false);
  return <details className="rounded-xl border border-line p-3" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="min-h-11 cursor-pointer content-center rounded-control text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">Charges</summary>
    {open ? <div className="mt-3"><LoanChargesSection makerspaceId={makerspaceId} requestId={requestId} inDisclosure /></div> : null}
  </details>;
}

function LoanChargesSection({ makerspaceId, requestId, inDisclosure = false }: {
  makerspaceId: number; requestId: number; inDisclosure?: boolean;
}) {
  const query = useLoanCharges(makerspaceId, requestId);
  const [waiving, setWaiving] = useState(false);
  const [revoking, setRevoking] = useState<LoanFeeWaiver | null>(null);
  const [openRow, setOpenRow] = useState<number | null>(null);
  const [notice, setNotice] = useState("");
  if (query.isLoading) return <p className="text-sm text-muted" role="status">Loading charges…</p>;
  if (query.error) {
    if (isHiddenError(query.error)) return inDisclosure ? <p className="text-sm text-muted">Charges are not available to you for this loan.</p> : null;
    return <p className="text-sm text-danger" role="alert">Couldn't load this loan's charges.{" "}
      <button className="desk-button-ghost underline" type="button" onClick={() => void query.refetch()}>Try again</button></p>;
  }
  const data = query.data as LoanCharges | undefined;
  if (!data || !Array.isArray(data.charges)) return null;
  // #184: with loan charges off nothing new can be raised; charges raised before the switch still list.
  const chargesOn = loanChargesOn(data);
  if (!chargesOn && !data.charges.length) return inDisclosure ? <p className="text-sm text-muted">Loan charges are off in this space.</p> : null;
  const rows = data.pricing_enabled && chargesOn ? data.accountability : [];
  const waivers = data.waivers_enabled ? data.waivers : [];

  return <section aria-label="Charges" className="grid gap-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      {inDisclosure ? <span /> : <h2 className="title-panel flex items-center gap-2"><Receipt aria-hidden="true" size={18} />Charges</h2>}
      {data.can_waive ? <button className="desk-button inline-flex items-center gap-2" type="button" onClick={() => setWaiving(true)}>
        <HandCoins aria-hidden="true" size={16} />Waive fees</button> : null}
    </div>
    {data.charges.length ? <ul className="grid gap-2">{data.charges.map(charge => <ChargeLine key={charge.id} charge={charge} />)}</ul>
      : <p className="text-sm text-muted">No charges on this loan.</p>}
    {rows.length ? <section aria-label="Damaged and lost items" className="grid gap-2">
      <h3 className="text-sm font-semibold text-ink">Damaged and lost items</h3>
      <ul className="grid gap-2">{rows.map(row => <li key={row.id} className="grid gap-2">
        {row.charge ? <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line p-3 text-sm">
          <span className="text-ink">{rowTitle(row)}</span>
          <span className="flex items-center gap-2"><span className="tabular-nums font-semibold text-ink">
            {formatMoney(row.charge.amount, row.charge.currency)}</span><StatusPill label={chargeStatus(row.charge.status)[0]} tone={chargeStatus(row.charge.status)[1]} /></span>
        </div> : openRow === row.id
          ? <AccountabilityChargeForm makerspaceId={makerspaceId} requestId={requestId} currency={data.currency} row={row}
            onDone={result => { setOpenRow(null); setNotice(result.free_reason === "waived" ? freeNotice("waived") : ""); }} />
          : <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line p-3 text-sm">
            <span className="text-ink">{rowTitle(row)} · <span className="text-muted">{row.no_charge_decided ? "No charge (decided)" : "no charge set"}</span></span>
            <button className="desk-button" type="button" aria-label={`Set charge for ${rowTitle(row)}`}
              onClick={() => setOpenRow(row.id)}>Set charge</button>
          </div>}
      </li>)}</ul>
      {notice ? <p className="text-sm text-muted" role="status">{notice}</p> : null}
    </section> : null}
    {waivers.length ? <WaiverHistory waivers={waivers} canRevoke={data.can_waive} onRevoke={setRevoking} /> : null}
    {waiving ? <WaiveFeesDialog makerspaceId={makerspaceId} requestId={requestId} charges={data.charges} onClose={() => setWaiving(false)} /> : null}
    {revoking ? <RevokeWaiverDialog makerspaceId={makerspaceId} requestId={requestId} waiver={revoking} onClose={() => setRevoking(null)} /> : null}
  </section>;
}
