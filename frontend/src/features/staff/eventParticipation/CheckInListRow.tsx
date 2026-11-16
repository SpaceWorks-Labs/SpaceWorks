import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "lucide-react";
import { staffRequest } from "../../../lib/api";
import { Card, StatusBadge } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { adminBase, useStaffCommand, type CheckInList, type ListEligibility } from "./api";

export const LIST_REASONS = (): Record<string, string> => ({
  not_confirmed: t`No confirmed place.`, entry_required: t`Check them in at the door first.`,
  not_eligible: t`Did not buy this add-on.`, already_collected: t`Already collected everything.`,
  waitlisted: t`On the waitlist. You can let them collect anyway, as at the entry desk.`,
});

/** "12 collected by 9 of 40 guests": the counts the server keeps per list (undone collections never count). */
export function listCounts(list: CheckInList) {
  return t`${list.collected} collected by ${list.collected_people ?? list.collected} of ${list.eligible ?? 0} guests`;
}

type Props = { eventId: number; list: CheckInList; canManage: boolean; first: boolean; last: boolean; onMove: (direction: -1 | 1) => void; moving: boolean };

/**
 * One check-in list (D22): its counts, the desk order, archive or restore, and collecting. A collection can be
 * undone for 60 seconds from the toast; a waitlisted guest collects only with an explicit override.
 */
export function CheckInListRow({ eventId, list, canManage, first, last, onMove, moving }: Props) {
  const client = useQueryClient();
  const command = useStaffCommand<CheckInList>(eventId), scan = useStaffCommand<ListEligibility>(eventId);
  const [open, setOpen] = useState(false), [registration, setRegistration] = useState("");
  const [result, setResult] = useState<ListEligibility | null>(null), [checked, setChecked] = useState(false);
  // Read-only eligibility check: answers "may they collect, and how often so far" without recording anything.
  const lookup = useMutation({ mutationFn: () => staffRequest<ListEligibility>(
    `${adminBase(eventId)}/checkin-lists/${list.id}/lookup/?registration_id=${encodeURIComponent(registration)}`) });
  const scanCode = (scan.error as { code?: string } | null)?.code ?? "";
  const undo = (value: ListEligibility) => async () => {
    await staffRequest(`${adminBase(eventId)}/checkin-lists/${list.id}/scan/${value.scan_id}/undo/`, { method: "POST", body: "{}" });
    setResult(null);
    await client.invalidateQueries({ queryKey: ["staff-event-participation", eventId] });
  };
  const collect = (override = false) => scan.mutate({ suffix: `/checkin-lists/${list.id}/scan/`, body: {
    operation_id: crypto.randomUUID(), registration_id: Number(registration), ...(override ? { override: true } : {}) } }, { onSuccess: value => {
    setResult(value); setChecked(false);
    const left = value.undo_until ? new Date(value.undo_until).getTime() - Date.now() : 0;
    toast(t`${value.name} collected from ${list.name}.`, left > 1000 && value.scan_id ? { undo: undo(value), undoKey: `checkin-list-scan-${value.scan_id}`, duration: Math.min(left, 60_000) } : {});
  } });
  const check = () => { scan.reset(); lookup.mutate(undefined, { onSuccess: value => { setResult(value); setChecked(true); } }); };
  return <li><Card><div className="grid gap-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0"><p className="font-semibold text-ink">{list.name}</p>
        <p className="text-sm tabular-nums text-muted">{listCounts(list)}{list.after_entry ? t` · after entry` : ""}
          {list.addon_name ? t` · buyers of ${list.addon_name}` : t` · ${list.per_person} per person`}</p></div>
      <div className="flex flex-wrap items-center gap-2">
        {list.archived ? <>
          <StatusBadge status="archived" label={t`Archived, read-only`} />
          {canManage ? <button type="button" className="desk-button" disabled={command.isPending}
            onClick={() => command.mutate({ suffix: `/checkin-lists/${list.id}/`, method: "PATCH", body: { restore: true } })}>{t`Restore`}</button> : null}
        </> : <>
          {canManage ? <>
            <button type="button" className="desk-button min-w-11 px-2" aria-label={t`Move ${list.name} up`} disabled={first || moving} onClick={() => onMove(-1)}><ArrowUp size={18} aria-hidden="true" /></button>
            <button type="button" className="desk-button min-w-11 px-2" aria-label={t`Move ${list.name} down`} disabled={last || moving} onClick={() => onMove(1)}><ArrowDown size={18} aria-hidden="true" /></button>
          </> : null}
          <button type="button" className="desk-button" aria-expanded={open} onClick={() => { setOpen(!open); setResult(null); lookup.reset(); scan.reset(); }}>{t`Collect`}</button>
          {canManage ? <button type="button" className="desk-button" disabled={command.isPending}
            onClick={() => command.mutate({ suffix: `/checkin-lists/${list.id}/`, method: "PATCH", body: { archive: true } })}>{t`Archive`}</button> : null}
        </>}
      </div>
    </div>
    {command.error ? <p role="alert" className="text-sm text-danger">{command.error.message}</p> : null}
    {open && !list.archived ? <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); collect(); }}>
      <label className="grid gap-1 text-sm text-ink">{t`Registration number`}<input className="desk-input" inputMode="numeric" required value={registration}
        onChange={e => { setRegistration(e.target.value.replace(/\D/g, "")); setResult(null); scan.reset(); }} /></label>
      <button type="button" className="desk-button" disabled={!registration || lookup.isPending} onClick={check}>{t`Check first`}</button>
      <button type="submit" className="desk-button" disabled={!registration || scan.isPending}>{t`Record collection`}</button>
      {scanCode === "waitlisted" ? <button type="button" className="desk-button-primary" disabled={scan.isPending} onClick={() => collect(true)}>{t`Let them collect anyway`}</button> : null}
      <div role="status" aria-live="polite" className="text-sm">
        {result ? <span className="text-ink">{t`${result.name}: ${result.used} of ${result.allowed} collected.`}
          {checked ? result.reason ? ` ${LIST_REASONS()[result.reason] ?? result.reason}` : t` Can collect now.` : ""}</span> : null}
        {lookup.error ? <span className="text-danger">{lookup.error.message}</span> : null}
        {scan.error ? <span className="text-danger">{LIST_REASONS()[scanCode] ?? scan.error.message}</span> : null}
      </div>
    </form> : null}
  </div></Card></li>;
}
