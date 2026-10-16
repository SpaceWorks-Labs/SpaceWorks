import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Field, Modal, SegmentedControl } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { presenceApi } from "./api";
import { presenceErrorText, presetLabel } from "./presenceCopy";

type MemberOption = { id: number; user: { id: number; username: string; display_name: string } };

/** Staff (or a staffed kiosk) checks a member in without location. The server picks the
 * status (visiting for members, guest for walk-ins) and records who did it in the audit log. */
export function StaffCheckInDialog({ makerspaceId, presets, onClose, onDone }: {
  makerspaceId: number; presets: number[]; onClose: () => void; onDone: () => void;
}) {
  const [query, setQuery] = useState("");
  const [accountId, setAccountId] = useState<number | null>(null);
  const [minutes, setMinutes] = useState(() => presets.includes(120) ? 120 : presets[0]);
  const search = query.trim();
  const members = useQuery({
    queryKey: ["presence", "staff", makerspaceId, "member-search", search],
    queryFn: () => staffRequest<{ results: MemberOption[] }>(`/admin/memberships?${new URLSearchParams({ makerspace_id: String(makerspaceId), status: "active", q: search })}`),
    enabled: search.length >= 2,
  });
  const checkIn = useMutation({ mutationFn: () => presenceApi.staffCheckIn(makerspaceId, { account_id: accountId!, duration_minutes: minutes }), onSuccess: onDone });
  const options = members.data?.results ?? [];
  return <Modal open onClose={onClose} title="Check someone in" footer={<div className="flex flex-wrap justify-end gap-3">
    <button type="button" className="desk-button" onClick={onClose}>Cancel</button>
    <button type="button" className="desk-button-brand" disabled={!accountId || checkIn.isPending} onClick={() => checkIn.mutate()}>{checkIn.isPending ? "Checking in…" : "Check in"}</button>
  </div>}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">Staff check-in doesn't need the person's location. Use it at the desk or kiosk when self check-in isn't possible.</p>
      <Field label="Find a member" hint="Type at least two letters of a name or username.">
        <input className="desk-input" type="search" value={query} onChange={(event) => { setQuery(event.target.value); setAccountId(null); }} />
      </Field>
      {members.isFetching ? <p role="status" className="text-sm text-muted">Searching…</p> : null}
      {members.isError ? <p role="alert" className="text-sm text-danger">{presenceErrorText(members.error).text}</p> : null}
      {search.length >= 2 && members.isSuccess && !options.length ? <p className="text-sm text-muted">No active members match.</p> : null}
      {options.length ? <fieldset className="grid gap-2"><legend className="text-sm font-semibold text-ink">Member</legend>
        {options.map((option) => <label key={option.id} className="flex min-h-11 items-center gap-3 text-sm">
          <input type="radio" name="presence-member" className="h-5 w-5 accent-accent" checked={accountId === option.user.id} onChange={() => setAccountId(option.user.id)} />
          <span>{option.user.display_name || option.user.username}<span className="text-muted"> · @{option.user.username}</span></span>
        </label>)}
      </fieldset> : null}
      <div className="grid gap-2"><span className="text-sm font-semibold text-ink">Duration</span>
        <SegmentedControl fullWidth label="Duration" value={String(minutes)} onChange={(value) => setMinutes(Number(value))}
          options={presets.map((value) => ({ value: String(value), label: presetLabel(value) }))} /></div>
      {checkIn.error ? <p role="alert" className="text-sm text-danger">{presenceErrorText(checkIn.error).text}</p> : null}
    </div>
  </Modal>;
}
