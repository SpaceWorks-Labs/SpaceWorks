import { t } from "@lingui/core/macro";
import { formatMinorMoney } from "../../../lib/money";
import { useState } from "react";
import { Field } from "../../../components/ui/Field";
import { Modal } from "../../../components/ui/Modal";
import type { PoolDetail } from "../../../generated/api";
import { commandError, usePrivateCommand, type EventScope } from "../../events/stagedForms/privateQueries";
import { reimbursementAdminKey, reimbursementAdminPath, useProgramme } from "./api";
import { MinorAmountInput } from "../../forms/MinorAmountInput";
import { BoxArt } from "../../../components/BoxSpinner";

/** The request queue row as the API sends it (the screening projection). */
export type ScreeningRow = { id: number; version: number; state: string; currency: string; kind?: string;
  budget?: { pool_id: number; pool_version: number; available_minor: number };
  award?: { id: number; state: string; amount_minor: number; reason_code?: string } | null };
type CrewPoolCommand = { expected_version: 0; initial_total_minor: number };
type BookingCommand = { expected_version: number; expected_pool_version: number; amount_minor: number; currency: string;
  vendor: string; booked_on: string; method: string; reference: string };
type CancelCommand = { expected_version: number; expected_pool_version: number; reason: string };

const METHODS = [["bank_transfer", "Bank transfer"], ["upi", "UPI"], ["card", "Card"], ["cash", "Cash"], ["cheque", "Cheque"],
  ["online", "Online"], ["other", "Other"]] as const;

export const isBookedTravel = (row: ScreeningRow) => row.award?.state === "closed" && row.award.reason_code === "direct_booking";
export const canBookTravel = (row: ScreeningRow) => ["requested", "waitlisted", "awarded"].includes(row.state)
  && (!row.award || row.award.state === "offered");

/** Hack-money G14: finance adds the one crew pool, so crew claims never eat the participant travel budget. */
export function CrewPoolPanel({ scope }: { scope: EventScope }) {
  const programme = useProgramme(scope);
  const command = usePrivateCommand<CrewPoolCommand>(reimbursementAdminKey(scope), true);
  const [total, setTotal] = useState<number | null>(null);
  const pools = ((programme.data as { pools?: PoolDetail[] } | undefined)?.pools) ?? [];
  const crew = pools.find(pool => pool.audience === "crew");
  const currency = programme.data?.pool?.currency ?? programme.data?.currency ?? "";
  if (!programme.data?.initialized) return null;
  return <section className="grid gap-3 rounded-2xl border border-line bg-panel p-5" aria-label={t`Crew budget`}>
    <h2 className="title-section">{t`Crew budget`}</h2>
    {crew ? <p>{t`Crew pool: total ${formatMinorMoney(crew.total_minor, crew.currency)}; available ${formatMinorMoney(crew.available_minor, crew.currency)}; reserved ${formatMinorMoney(crew.reserved_minor, crew.currency)}; committed ${formatMinorMoney(crew.committed_minor, crew.currency)}. Crew awards reserve from this pool.`}</p> : <>
      <p className="text-sm text-muted">{t`Optional. With a crew pool, crew reimbursement awards reserve from it and leave the participant pool alone.`}</p>
      <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault();
        command.mutate({ path: `${reimbursementAdminPath(scope)}crew-pool/`, body: { expected_version: 0, initial_total_minor: total ?? Number.NaN } }); }}>
        <Field label={currency ? t`Crew pool total (${currency})` : t`Crew pool total`}><MinorAmountInput required currency={currency}
          value={total} onChange={setTotal} /></Field>
        <button type="submit" className="desk-button" disabled={command.isPending}>{t`Create crew pool`}</button>
      </form></>}
    {command.error ? <p role="alert">{commandError(command.error)}</p> : command.isSuccess ? <p role="status">{t`Crew pool created.`}</p> : null}
  </section>;
}

/** Hack-money G12: travel the organiser booked and paid for. It closes the request as a direct booking, commits the
 *  budget and records a ledger expense; nobody is sent money. Cancelling voids the expense and frees the budget. */
export function BookedTravelActions({ scope, row }: { scope: EventScope; row: ScreeningRow }) {
  const [open, setOpen] = useState<"" | "record" | "cancel">("");
  if (!row.budget || (!isBookedTravel(row) && !canBookTravel(row))) return null;
  return <>
    {isBookedTravel(row)
      ? <button type="button" className="desk-button-ghost justify-self-start" onClick={() => setOpen("cancel")}>{t`Cancel booked travel`}</button>
      : <button type="button" className="desk-button justify-self-start" onClick={() => setOpen("record")}>{t`Record booked travel`}</button>}
    {open ? <BookingModal scope={scope} row={row} cancel={open === "cancel"} onClose={() => setOpen("")} /> : null}
  </>;
}

function BookingModal({ scope, row, cancel, onClose }: { scope: EventScope; row: ScreeningRow; cancel: boolean; onClose: () => void }) {
  const record = usePrivateCommand<BookingCommand>(reimbursementAdminKey(scope), true);
  const undo = usePrivateCommand<CancelCommand>(reimbursementAdminKey(scope), true);
  const [amount, setAmount] = useState<number | null>(null); const [vendor, setVendor] = useState("");
  const [bookedOn, setBookedOn] = useState(new Date().toISOString().slice(0, 10)); const [method, setMethod] = useState("bank_transfer");
  const [reference, setReference] = useState(""); const [reason, setReason] = useState("");
  const base = `${reimbursementAdminPath(scope)}requests/${row.id}/direct-booking/`;
  const poolVersion = row.budget?.pool_version ?? 0;
  const pending = record.isPending || undo.isPending;
  const submit = () => cancel
    ? undo.mutate({ path: `${base}cancel/`, body: { expected_version: row.version, expected_pool_version: poolVersion, reason } }, { onSuccess: onClose })
    : record.mutate({ path: base, body: { expected_version: row.version, expected_pool_version: poolVersion, amount_minor: amount ?? Number.NaN,
      currency: row.currency, vendor, booked_on: bookedOn, method, reference } }, { onSuccess: onClose });
  return <Modal open title={cancel ? t`Cancel booked travel` : t`Record booked travel`} onClose={() => { if (!pending) onClose(); }}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); submit(); }}>
      <fieldset disabled={pending} className="grid gap-4"><legend className="sr-only">{cancel ? t`Cancel booking` : t`Booking`}</legend>
        {cancel ? <><p>{t`The travel expense is voided and its budget released. The request is closed as declined.`}</p>
          <Field label={t`Reason`}><input className="desk-input" required maxLength={300} value={reason} onChange={event => setReason(event.target.value)} /></Field></> : <>
          <p>{t`Record travel the space booked and paid for directly. The person files no claim and nobody is sent money. Available: ${formatMinorMoney(row.budget?.available_minor, row.currency)}.`}</p>
          <Field label={t`Cost (${row.currency})`}><MinorAmountInput required currency={row.currency}
            value={amount} onChange={setAmount} /></Field>
          <Field label={t`Vendor`} hint={t`The airline, bus operator or agent the space paid.`}><input className="desk-input" required maxLength={150}
            value={vendor} onChange={event => setVendor(event.target.value)} /></Field>
          <Field label={t`Booked on`}><input className="desk-input" type="date" required value={bookedOn} onChange={event => setBookedOn(event.target.value)} /></Field>
          <Field label={t`Paid by`}><select className="desk-input" value={method} onChange={event => setMethod(event.target.value)}>
            {METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
          <Field label={t`Booking reference (optional)`}><input className="desk-input" maxLength={64} value={reference} onChange={event => setReference(event.target.value)} /></Field></>}
        <button type="submit" className="desk-button-primary">{pending ? <><BoxArt size={16} mono />{t`Saving…`}</> : cancel ? t`Cancel booking` : t`Record booking`}</button>
      </fieldset>
      {record.error || undo.error ? <p role="alert">{commandError(record.error || undo.error)}</p> : null}
    </form></Modal>;
}
