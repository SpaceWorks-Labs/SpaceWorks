import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field, StatusPill } from "../../../components/ui";
import { formatDate } from "../../../lib/format";
import { guestErrorText } from "../../guestPasses/api";
import { MembershipPagination } from "../../staff/MembershipPagination";
import { communityKeys, communityStaffApi } from "../api";
import { entryStatusLabel, hoursLabel } from "../labels";
import { VolunteerCredits } from "./VolunteerCredits";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";

/** Members › Volunteering (decision 223 k): approve logged hours, import verified event shifts, credits. */
export function VolunteerQueue({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const [log, setLog] = useState({ member: "", minutes: "", day: "", description: "" });
  const hours = useQuery({ queryKey: communityKeys.hours(makerspaceId, status, page), queryFn: () => communityStaffApi.hours(makerspaceId, status, page) });
  const refresh = () => client.invalidateQueries({ queryKey: communityKeys.all(makerspaceId) });
  const decide = useMutation({ mutationFn: ({ id, approve }: { id: number; approve: boolean }) => communityStaffApi.decide(makerspaceId, id, approve), onSuccess: refresh });
  const importShifts = useMutation({ mutationFn: () => communityStaffApi.importShifts(makerspaceId), onSuccess: refresh });
  const add = useMutation({
    mutationFn: () => communityStaffApi.logHours(makerspaceId, { member_id: Number(log.member), minutes: Number(log.minutes), worked_on: log.day, description: log.description.trim() }),
    onSuccess: () => { setLog({ member: "", minutes: "", day: "", description: "" }); void refresh(); },
  });
  const rows = hours.data?.results ?? [];
  const error = decide.error ?? importShifts.error ?? add.error;
  return <div className="grid gap-5">
    <section aria-label={t`Volunteer hours`} className="grid gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <label className="grid gap-1 text-xs text-muted">{t`Show`}
          <select className="desk-input min-h-11" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
            <option value="pending">{entryStatusLabel("pending")}</option><option value="approved">{entryStatusLabel("approved")}</option>
            <option value="rejected">{entryStatusLabel("rejected")}</option><option value="">{t`All`}</option></select></label>
        <button type="button" className="desk-button min-h-11" disabled={importShifts.isPending} onClick={() => importShifts.mutate()}>{importShifts.isPending ? <><BoxArt size={16} mono />{t`Importing…`}</> : t`Offer verified event shifts`}</button>
      </div>
      {importShifts.data ? <p role="status" className="text-sm text-muted">{t`${importShifts.data.created} shift entries added for approval.`}</p> : null}
      {hours.isLoading ? <LogoLoader label={t`Loading volunteer hours…`} size={48} className="min-h-16 py-3" /> : null}
      {hours.isError ? <p role="alert" className="text-sm text-danger">{guestErrorText(hours.error)}</p> : null}
      {hours.isSuccess && !rows.length ? <EmptyState message={status === "pending" ? t`Nothing waiting for approval.` : t`No volunteer hours here.`} /> : null}
      <ul className="grid gap-3">
        {rows.map((row) => <li key={row.id} className="flex flex-wrap items-start gap-3 rounded-2xl border border-line bg-panel p-4">
          <div className="min-w-0 flex-1 basis-56">
            <p className="title-section break-words">{row.member_name}</p>
            <p className="text-sm text-muted">{hoursLabel(row.minutes)} · {formatDate(row.worked_on)}{row.source === "event_shift" ? ` · ${t`Event shift`}` : ""}</p>
            {row.description ? <p className="text-sm text-ink">{row.description}</p> : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill tone={row.status === "approved" ? "success" : row.status === "rejected" ? "danger" : "warn"} label={entryStatusLabel(row.status)} />
            {row.status === "pending" ? <>
              <button type="button" className="desk-button-primary min-h-11" disabled={decide.isPending} onClick={() => decide.mutate({ id: row.id, approve: true })}>{t`Approve`}</button>
              <button type="button" className="desk-button-ghost min-h-11" disabled={decide.isPending} onClick={() => decide.mutate({ id: row.id, approve: false })}>{t`Reject`}</button>
            </> : null}
          </div>
        </li>)}
      </ul>
      <MembershipPagination label={t`volunteer hours`} page={page} next={hours.data?.next} previous={hours.data?.previous} fetching={hours.isFetching} onPage={setPage} />
    </section>
    <form aria-label={t`Log hours for a member`} className="grid gap-3 rounded-2xl border border-line p-4" onSubmit={(event) => { event.preventDefault(); add.mutate(); }}>
      <h3 className="title-section">{t`Log hours for a member`}</h3>
      <p className="text-sm text-muted">{t`Hours you log are approved at once and may convert into a credit.`}</p>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t`Member's account number`}><input className="desk-input" inputMode="numeric" value={log.member} onChange={(event) => setLog({ ...log, member: event.target.value.replace(/\D/g, "") })} /></Field>
        <Field label={t`Minutes`}><input className="desk-input" type="number" min={1} max={1440} value={log.minutes} onChange={(event) => setLog({ ...log, minutes: event.target.value })} /></Field>
        <Field label={t`Day`}><input className="desk-input" type="date" value={log.day} onChange={(event) => setLog({ ...log, day: event.target.value })} /></Field>
      </div>
      <Field label={t`What they did (optional)`}><input className="desk-input" maxLength={200} value={log.description} onChange={(event) => setLog({ ...log, description: event.target.value })} /></Field>
      <div><button type="submit" className="desk-button min-h-11" disabled={!log.member || !Number(log.minutes) || !log.day || add.isPending}>{add.isPending ? t`Saving…` : t`Log hours`}</button></div>
    </form>
    {error ? <p role="alert" className="text-sm text-danger">{guestErrorText(error)}</p> : null}
    <VolunteerCredits makerspaceId={makerspaceId} />
  </div>;
}
