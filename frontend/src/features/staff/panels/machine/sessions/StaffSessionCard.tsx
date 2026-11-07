import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill } from "../../../../../components/ui";
import { money } from "../../../../payments/usePriceQuote";
import { sessionErrorMessage, sessionKeys, staffSessionAction, type StaffSession } from "../../../../machine-sessions/api";
import { CHARGE_LABELS, duration, SOURCES, STOP_REASONS, when } from "../../../../machine-sessions/sessionFormat";
import { SessionMemberSelect } from "./SessionMemberSelect";

type Mode = "idle" | "correct" | "assign";

function statusPill(session: StaffSession) {
  if (session.status === "live") return <StatusPill tone="info" icon="Clock" label={t`Live`} />;
  if (session.needs_review) return <StatusPill tone="warn" label={session.member_id ? t`Check the time` : t`Unattributed`} />;
  const charge = CHARGE_LABELS[session.charge_state];
  return <StatusPill tone={charge.tone} label={charge.text} />;
}

/** One session for staff: who, which machine, how long, and the next step (stop, correct, assign, confirm). */
export function StaffSessionCard({ session, makerspaceId }: { session: StaffSession; makerspaceId: number }) {
  const client = useQueryClient();
  const [mode, setMode] = useState<Mode>("idle");
  const [minutes, setMinutes] = useState(String(session.minutes));
  const [reason, setReason] = useState("");
  const [member, setMember] = useState("");
  const action = useMutation({
    mutationFn: ({ name, body }: { name: "stop" | "confirm" | "amend" | "assign"; body?: unknown }) => staffSessionAction(session.id, name, body),
    onSuccess: () => { setMode("idle"); setReason(""); void client.invalidateQueries({ queryKey: sessionKeys.staffAll(makerspaceId) }); },
  });
  const busy = action.isPending;
  const corrections = session.amendments.filter(row => row.kind === "correct");
  return <li className="grid gap-3 rounded-2xl border border-line bg-panel p-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="title-section break-words">{session.member_name || t`No member yet`} · {session.machine_name}</p>
        <p className="mt-1 text-sm text-muted [overflow-wrap:anywhere]">
          {when(session.started_at)} · {duration(session.minutes)} · {SOURCES[session.source]}
          {session.stop_reason ? ` · ${STOP_REASONS[session.stop_reason] ?? session.stop_reason}` : ""}
          {session.amount != null && session.rate ? ` · ${money(session.amount, session.rate.currency)}` : ""}
          {session.service_request_id ? t` · job #${session.service_request_id}` : ""}
        </p>
        {corrections.length ? <p className="mt-1 text-sm text-muted">{t`Corrected from ${duration(session.duration_minutes)}:${" "}${corrections[corrections.length - 1].reason} (${corrections[corrections.length - 1].actor_name})`}</p> : null}
      </div>
      {statusPill(session)}
    </div>
    {mode === "correct" ? <form className="grid gap-2 sm:grid-cols-[8rem_1fr_auto] sm:items-end" onSubmit={event => {
      event.preventDefault(); action.mutate({ name: "amend", body: { minutes: Number(minutes), reason: reason.trim() } }); }}>
      <label className="eyebrow grid gap-1">{t`Minutes`}<input className="desk-input" type="number" min={0} max={1440} required
        value={minutes} onChange={event => setMinutes(event.target.value)} /></label>
      <label className="eyebrow grid gap-1">{t`Reason`}<input className="desk-input" required maxLength={500} value={reason}
        onChange={event => setReason(event.target.value)} placeholder={t`Why the time changes`} /></label>
      <button className="desk-button-primary" disabled={busy}>{busy ? t`Saving…` : t`Save correction`}</button>
    </form> : null}
    {mode === "assign" ? <form className="grid gap-2" onSubmit={event => {
      event.preventDefault(); action.mutate({ name: "assign", body: { member_id: Number(member), reason: reason.trim() } }); }}>
      <SessionMemberSelect machineId={session.machine_id} value={member} onChange={setMember} />
      <label className="eyebrow grid gap-1">{t`Reason`}<input className="desk-input" required maxLength={500} value={reason}
        onChange={event => setReason(event.target.value)} placeholder={t`How you know whose session it was`} /></label>
      <button className="desk-button-primary justify-self-start" disabled={busy || !member}>{busy ? t`Saving…` : t`Assign`}</button>
    </form> : null}
    <div className="flex flex-wrap gap-2">
      {session.status === "live" ? <button type="button" className="desk-button" disabled={busy}
        onClick={() => action.mutate({ name: "stop" })}>{busy ? t`Stopping…` : t`Stop session`}</button> : null}
      {session.needs_review && mode === "idle" ? <>
        {session.member_id ? <button type="button" className="desk-button-primary" disabled={busy}
          onClick={() => action.mutate({ name: "confirm" })}>{busy ? t`Confirming…` : t`Confirm`}</button> : null}
        <button type="button" className="desk-button" onClick={() => setMode("correct")}>{t`Correct time`}</button>
        {!session.member_id ? <button type="button" className="desk-button" onClick={() => setMode("assign")}>{t`Assign member`}</button> : null}
      </> : null}
      {mode !== "idle" ? <button type="button" className="desk-button" onClick={() => setMode("idle")}>{t`Cancel`}</button> : null}
    </div>
    {action.isError ? <p role="alert" className="text-sm text-danger">{sessionErrorMessage(action.error)}</p> : null}
  </li>;
}
