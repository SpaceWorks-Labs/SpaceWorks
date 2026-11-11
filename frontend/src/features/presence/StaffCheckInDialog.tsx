import { t } from "@lingui/core/macro";
import { useContext, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Field, Modal, SegmentedControl } from "../../components/ui";
import { staffRequest, StructuredApiError } from "../../lib/api";
import { capabilityOn } from "../../lib/features";
import { StaffListContext } from "../staff/StaffListContext";
import { formatDate } from "../../lib/format";
import { presenceApi } from "./api";
import { presenceErrorText, presetLabel } from "./presenceCopy";

type MemberOption = { id: number; user: { id: number; username: string; display_name: string } };
type Person = { id: number; name: string; detail: string; guest: boolean; waiverOnFile: boolean };

/** Live guest-pass holders matching the search (0.12.0). Answers [] when the server refuses (guest
 *  passes off, or no authority), so the dialog stays a member search. */
async function liveGuests(makerspaceId: number, search: string) {
  try { return (await presenceApi.checkInGuests(makerspaceId, search)).results ?? []; } catch { return []; }
}

/** Staff (or a staffed kiosk) checks a member or guest-pass holder in without location. The server
 * picks the status (visiting for members, guest for pass holders) and records who did it. */
export function StaffCheckInDialog({ makerspaceId, presets, onClose, onDone }: {
  makerspaceId: number; presets: number[]; onClose: () => void; onDone: () => void;
}) {
  const [query, setQuery] = useState("");
  const [accountId, setAccountId] = useState<number | null>(null);
  const [deskWaiver, setDeskWaiver] = useState(false);
  const [minutes, setMinutes] = useState(() => presets.includes(120) ? 120 : presets[0]);
  const search = query.trim();
  const members = useQuery({
    queryKey: ["presence", "staff", makerspaceId, "member-search", search],
    queryFn: () => staffRequest<{ results: MemberOption[] }>(`/admin/memberships?${new URLSearchParams({ makerspace_id: String(makerspaceId), status: "active", q: search })}`),
    enabled: search.length >= 2,
  });
  // Decision 218: with guest passes off the guest search is never asked (the server would 404 it).
  const { makerspace } = useContext(StaffListContext);
  const guestPassesOff = makerspace?.id === makerspaceId && !capabilityOn(makerspace, "membership.guest_passes");
  const guests = useQuery({ queryKey: ["presence", "staff", makerspaceId, "guest-search", search], queryFn: () => liveGuests(makerspaceId, search), enabled: search.length >= 2 && !guestPassesOff });
  const checkIn = useMutation({
    mutationFn: () => presenceApi.staffCheckIn(makerspaceId, { account_id: accountId!, duration_minutes: minutes, ...(deskWaiver ? { waiver_accepted_at_desk: true } : {}) }),
    onSuccess: onDone,
  });
  const options: Person[] = [
    ...(members.data?.results ?? []).map((option) => ({ id: option.user.id, name: option.user.display_name || option.user.username, detail: `@${option.user.username}`, guest: false, waiverOnFile: true })),
    ...(guests.data ?? []).map((row) => ({ id: row.id, name: row.display_name, guest: true, waiverOnFile: row.waiver_on_file,
      detail: `${t`Guest pass until ${formatDate(row.pass_valid_until)}`} · ${row.waiver_on_file ? t`waiver on file` : t`no waiver yet`}` })),
  ].filter((option, index, all) => all.findIndex((other) => other.id === option.id) === index);
  const chosen = options.find((option) => option.id === accountId);
  const waiverRefused = checkIn.error instanceof StructuredApiError && checkIn.error.code === "waiver_acceptance_required";
  return <Modal open onClose={onClose} title={t`Check someone in`} footer={<div className="flex flex-wrap justify-end gap-3">
    <button type="button" className="desk-button" onClick={onClose}>{t`Cancel`}</button>
    <button type="button" className="desk-button-brand" disabled={!accountId || checkIn.isPending} onClick={() => checkIn.mutate()}>{checkIn.isPending ? t`Checking in…` : t`Check in`}</button>
  </div>}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">{t`Staff check-in doesn't need the person's location. Use it at the desk or kiosk when self check-in isn't possible.`}</p>
      <Field label={t`Find a member or guest`} hint={t`Type at least two letters of a name or username.`}>
        <input className="desk-input" type="search" value={query} onChange={(event) => { setQuery(event.target.value); setAccountId(null); setDeskWaiver(false); }} />
      </Field>
      {members.isFetching || guests.isFetching ? <p role="status" className="text-sm text-muted">{t`Searching…`}</p> : null}
      {members.isError ? <p role="alert" className="text-sm text-danger">{presenceErrorText(members.error).text}</p> : null}
      {search.length >= 2 && members.isSuccess && guests.isSuccess && !options.length ? <p className="text-sm text-muted">{t`No active members or guest-pass holders match.`}</p> : null}
      {options.length ? <fieldset className="grid gap-2"><legend className="text-sm font-semibold text-ink">{t`Person`}</legend>
        {options.map((option) => <label key={option.id} className="flex min-h-11 items-center gap-3 text-sm">
          <input type="radio" name="presence-member" className="h-5 w-5 accent-accent" checked={accountId === option.id} onChange={() => { setAccountId(option.id); setDeskWaiver(false); }} />
          <span>{option.name}<span className="text-muted"> · {option.detail}</span></span>
        </label>)}
      </fieldset> : null}
      {chosen?.guest && !chosen.waiverOnFile ? <label className="flex min-h-11 items-center gap-3 text-sm">
        <input type="checkbox" className="h-5 w-5 accent-accent" checked={deskWaiver} onChange={(event) => setDeskWaiver(event.target.checked)} />
        {t`Waiver accepted at the desk`}</label> : null}
      <div className="grid gap-2"><span className="text-sm font-semibold text-ink">{t`Duration`}</span>
        <SegmentedControl fullWidth label={t`Duration`} value={String(minutes)} onChange={(value) => setMinutes(Number(value))}
          options={presets.map((value) => ({ value: String(value), label: presetLabel(value) }))} /></div>
      {checkIn.error ? <p role="alert" className="text-sm text-danger">{waiverRefused
        ? t`This guest hasn't accepted the waiver. Once they have read and accepted it, tick "Waiver accepted at the desk" and try again.`
        : presenceErrorText(checkIn.error).text}</p> : null}
    </div>
  </Modal>;
}
