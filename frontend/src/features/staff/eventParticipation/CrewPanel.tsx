import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Card, ErrorText, StatusBadge } from "../../../components/ui";
import { useStaffCommand, useStaffQuery, type Catering, type CrewRow, type Switches } from "./api";

/**
 * The event crew (#128 C-36). A crew place is free and never counts against capacity. Being on
 * the crew gives no staff access: desks still need their own role. The catering summary counts
 * dietary needs only; it never says who has which (#28).
 */
export function CrewPanel({ eventId, signupUrl }: { eventId: number; signupUrl: string }) {
  const roster = useStaffQuery<CrewRow[]>(eventId, "/crew/");
  const catering = useStaffQuery<Catering>(eventId, "/crew/catering/");
  const switches = useStaffQuery<Switches>(eventId, "/participation-settings/");
  const command = useStaffCommand<CrewRow>(eventId), save = useStaffCommand<Switches>(eventId);
  const [member, setMember] = useState(""), [role, setRole] = useState("");
  const toggle = (key: keyof Switches, value: boolean) =>
    save.mutate({ suffix: "/participation-settings/", method: "PATCH", body: { [key]: value } });
  const error = roster.error ?? command.error ?? save.error;
  const live = (roster.data ?? []).filter(row => ["applied", "approved"].includes(row.state));
  return <section className="grid gap-4" aria-labelledby="crew-heading">
    <header className="grid gap-1">
      <h3 id="crew-heading" className="text-lg font-semibold text-ink">{t`Crew`}</h3>
      <p className="text-sm text-muted">{t`Crew places are free and never use the event's capacity.`}</p>
    </header>
    {error ? <ErrorText message={error.message} /> : null}
    {switches.data ? <Card><fieldset className="grid gap-1">
      <legend className="text-sm font-semibold text-ink">{t`Sign-up link`}</legend>
      {([["crew_signup_open", "Open the crew sign-up link"], ["crew_approval_required", "Review each sign-up before approving"],
        ["crew_public_section", "Show crew who opted in on the event page (public profiles only)"]] as const).map(([key, label]) =>
        <label key={key} className="flex min-h-11 items-center gap-3 text-sm text-ink">
          <input type="checkbox" checked={switches.data![key]} disabled={save.isPending} onChange={e => toggle(key, e.target.checked)} />{label}</label>)}
      {switches.data.crew_signup_open ? <p className="break-all text-sm text-muted">{t`Share: `}<a className="underline" href={signupUrl}>{signupUrl}</a></p> : null}
    </fieldset></Card> : null}
    {roster.isLoading ? <p role="status">{t`Loading crew…`}</p> : null}
    {roster.data?.length === 0 ? <p className="text-sm text-muted">{t`Nobody is on the crew yet.`}</p> : null}
    <ul className="grid gap-2">{live.map(row => <li key={row.id}><Card><div className="flex flex-wrap items-center justify-between gap-3">
      <div><p className="font-semibold text-ink">{row.name}</p>
        <p className="text-sm text-muted">{row.crew_role || t`Crew`}{row.has_place ? t` · crew place` : ""}</p></div>
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={row.state} label={row.state === "applied" ? t`Waiting for review` : t`On the crew`} />
        {row.state === "applied" ? <>
          <button type="button" className="desk-button" disabled={command.isPending} onClick={() => command.mutate({
            suffix: `/crew/${row.id}/decide/`, body: { approve: true, expected_version: row.version } })}>{t`Approve`}</button>
          <button type="button" className="desk-button" disabled={command.isPending} onClick={() => command.mutate({
            suffix: `/crew/${row.id}/decide/`, body: { approve: false, expected_version: row.version } })}>{t`Decline`}</button>
        </> : <button type="button" className="desk-button" disabled={command.isPending}
          onClick={() => command.mutate({ suffix: `/crew/${row.id}/remove/` })}>{t`Remove`}</button>}
      </div></div></Card></li>)}</ul>
    <Card><form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault();
      command.mutate({ suffix: "/crew/", body: { member_id: Number(member), crew_role: role } }, { onSuccess: () => { setMember(""); setRole(""); } }); }}>
      <label className="grid gap-1 text-sm text-ink">{t`Account number`}<input className="desk-input" inputMode="numeric" required value={member} onChange={e => setMember(e.target.value.replace(/\D/g, ""))} /></label>
      <label className="grid gap-1 text-sm text-ink">{t`Role (optional)`}<input className="desk-input" maxLength={60} value={role} onChange={e => setRole(e.target.value)} placeholder={t`Door, AV, mentor`} /></label>
      <button type="submit" className="desk-button" disabled={!member || command.isPending}>{t`Add to crew`}</button>
    </form></Card>
    {catering.data ? <Card><div className="grid gap-1">
      <p className="font-semibold text-ink">{t`Catering`}</p>
      <p className="text-sm text-muted">{t`${catering.data.approved} crew, ${catering.data.with_needs} with dietary needs.`}</p>
      <ul className="grid gap-1">{catering.data.needs.map(need => <li key={need.label} className="text-sm text-ink">{need.label}: {need.count}</li>)}</ul>
    </div></Card> : null}
  </section>;
}
