import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Card, StatusPill } from "../../components/ui";
import { useEventTicketing, type EventCode } from "./eventTicketingApi";
import { EventBulkInvites } from "./EventBulkInvites";
import { EventPanelPager } from "./EventPanelPager";
import { panelEmpty, panelField, panelInput, panelReveal, panelRow } from "./eventPanelStyles";

export function EventInvitesPanel({ visible = true,  eventId, disabled = false }: { visible?: boolean;  eventId: number; disabled?: boolean }) {
  const [page, setPage] = useState(1);
  const { rows, create, revoke } = useEventTicketing<EventCode>(eventId, "invites", page);
  const [email, setEmail] = useState("");
  const [limit, setLimit] = useState(1);
  const [expires, setExpires] = useState("");
  const [code, setCode] = useState("");
  const error = rows.error || create.error || revoke.error;
  if (!visible) return null;
  return <section className="grid gap-4" aria-label={t`Event invitations`}>
    <h3 className="title-section">{t`Invitations`}</h3>
    <Card><EventBulkInvites eventId={eventId} disabled={disabled} /></Card>
    <Card><form className="grid gap-4" aria-label={t`Invitation code`} onSubmit={(e) => { e.preventDefault(); create.mutate({ email, max_uses: limit, expires_at: expires ? new Date(expires).toISOString() : null }, { onSuccess: (row) => setCode(row.code ?? "") }); }}>
      <label className={panelField}>{t`Recipient email (optional)`}<input className={panelInput} type="email" autoComplete="email" value={email} disabled={disabled} onChange={(e) => setEmail(e.target.value)} /></label>
      <label className={panelField}>{t`Maximum uses`}<input className={panelInput} type="number" min="1" required value={limit} disabled={disabled} onChange={(e) => setLimit(Number(e.target.value))} /></label>
      <label className={panelField}>{t`Expires`}<input className={panelInput} type="datetime-local" value={expires} disabled={disabled} onChange={(e) => setExpires(e.target.value)} /></label>
      <button className="desk-button-primary justify-self-start" type="submit" disabled={disabled || create.isPending}>{t`Create invitation`}</button>
    </form></Card>
    {code ? <div role="status" className={panelReveal}><p>{t`Copy this code now. It is shown once.`}</p><output className="break-all code-text">{code}</output><button className="desk-button" type="button" onClick={() => setCode("")}>{t`Hide code`}</button></div> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
    {rows.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading invitations…`}</p> : null}
    {rows.data?.results.length === 0 ? <p className={panelEmpty}>{t`No invitation codes yet.`}</p> : null}
    {rows.data?.results.length ? <ul className="grid gap-3">{rows.data.results.map((row) => <li key={row.id} className={panelRow}>
      <div className="min-w-0"><p className="title-section">{t`Invitation ${row.id}`}</p><p className="mt-1 text-sm tabular-nums text-muted">{row.uses}/{row.max_uses} uses</p></div>
      {row.revoked_at ? <StatusPill label={t`Revoked`} /> : <button className="desk-button-danger-outline" type="button" disabled={disabled || revoke.isPending} onClick={() => revoke.mutate(row.id)}>{t`Revoke invitation ${row.id}`}</button>}
    </li>)}</ul> : null}
    <EventPanelPager page={page} setPage={setPage} previous={rows.data?.previous} next={rows.data?.next} />
  </section>;
}
