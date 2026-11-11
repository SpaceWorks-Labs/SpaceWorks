import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field, StatusPill } from "../../../components/ui";
import { formatDate } from "../../../lib/format";
import { guestErrorText } from "../../guestPasses/api";
import { communityKeys, communityMemberApi } from "../api";
import { creditLabel, creditStatusLabel, entryStatusLabel, hoursLabel } from "../labels";

/** A member's volunteer hours and the credits they earned (decision 223 k). Hidden when the feature is off. */
export function VolunteerLog({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [form, setForm] = useState({ minutes: "", day: "", description: "" });
  const hours = useQuery({ queryKey: communityKeys.myHours(makerspaceId), queryFn: () => communityMemberApi.hours(makerspaceId), retry: false });
  const credits = useQuery({ queryKey: communityKeys.myCredits(makerspaceId), queryFn: () => communityMemberApi.credits(makerspaceId), retry: false, enabled: hours.isSuccess });
  const log = useMutation({
    mutationFn: () => communityMemberApi.logHours(makerspaceId, { minutes: Number(form.minutes), worked_on: form.day, description: form.description.trim() }),
    onSuccess: () => { setForm({ minutes: "", day: "", description: "" }); void client.invalidateQueries({ queryKey: communityKeys.myHours(makerspaceId) }); },
  });
  if (hours.isError) return null;
  const entries = hours.data ?? [];
  const available = (credits.data ?? []).filter((row) => row.status === "available");
  return <section aria-labelledby="volunteer-log-title" className="desk-panel grid gap-4 p-5">
    <div><h2 id="volunteer-log-title" className="title-panel">{t`Volunteering`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Log the time you gave. Once staff approve it, hours can earn a credit on your next membership charge.`}</p></div>
    {available.length ? <p className="text-sm text-success-ink">{t`Credits waiting for your next charge: ${available.map(creditLabel).join(", ")}`}</p> : null}
    <form className="grid gap-3" aria-label={t`Log volunteer hours`} onSubmit={(event) => { event.preventDefault(); log.mutate(); }}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t`Minutes`}><input className="desk-input" type="number" min={1} max={1440} value={form.minutes} onChange={(event) => setForm({ ...form, minutes: event.target.value })} /></Field>
        <Field label={t`Day`}><input className="desk-input" type="date" value={form.day} onChange={(event) => setForm({ ...form, day: event.target.value })} /></Field>
      </div>
      <Field label={t`What you did (optional)`}><input className="desk-input" maxLength={200} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></Field>
      <div><button type="submit" className="desk-button-brand min-h-11" disabled={!Number(form.minutes) || !form.day || log.isPending}>{log.isPending ? t`Sending…` : t`Send for approval`}</button></div>
      {log.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(log.error)}</p> : null}
    </form>
    {hours.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading your hours…`}</p> : null}
    {entries.length ? <ul className="grid gap-2" aria-label={t`Your volunteer hours`}>
      {entries.map((row) => <li key={row.id} className="flex flex-wrap items-center gap-2 rounded-control border border-line p-3 text-sm">
        <span className="min-w-0 flex-1 basis-40 text-ink">{hoursLabel(row.minutes)} · {formatDate(row.worked_on)}{row.description ? <span className="text-muted"> · {row.description}</span> : null}</span>
        <StatusPill tone={row.status === "approved" ? "success" : row.status === "rejected" ? "danger" : "warn"} label={entryStatusLabel(row.status)} />
      </li>)}
    </ul> : hours.isSuccess ? <p className="text-sm text-muted">{t`No hours logged yet.`}</p> : null}
    {credits.data?.some((row) => row.status !== "available") ? <details className="text-sm"><summary className="cursor-pointer text-muted">{t`Credit history`}</summary>
      <ul className="mt-2 grid gap-1 text-muted">{credits.data.filter((row) => row.status !== "available").map((row) => <li key={row.id}>{creditLabel(row)} · {creditStatusLabel(row.status)}{row.member_name ? ` · ${row.member_name}` : ""}</li>)}</ul>
    </details> : null}
  </section>;
}
