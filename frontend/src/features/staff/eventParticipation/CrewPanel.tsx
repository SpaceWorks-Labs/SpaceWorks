import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Card, ErrorText } from "../../../components/ui";
import { useStaffCommand, useStaffQuery, type Catering, type CrewKind, type CrewRow, type Switches } from "./api";
import { CREW_KINDS, CrewRowCard, crewKindLabel } from "./CrewRowCard";
import { useCrewOrder } from "./useCrewOrder";

/**
 * The event crew (#128 C-36). A crew place is free and never counts against capacity. Being on
 * the crew gives no staff access: desks still need their own role. The catering summary counts
 * dietary needs only; it never says who has which (#28). C8/C13 (E-F4): staff edit the role, the
 * kind (`events.crew_kinds`) and public visibility, and set the crew's order by drag or with the arrows.
 */
export function CrewPanel({ eventId, signupUrl, kinds = false }: { eventId: number; signupUrl: string; kinds?: boolean }) {
  const [kind, setKind] = useState<CrewKind | "">("");
  const filtered = kinds && !!kind;
  const roster = useStaffQuery<CrewRow[]>(eventId, filtered ? `/crew/?kind=${kind}` : "/crew/");
  const catering = useStaffQuery<Catering>(eventId, "/crew/catering/");
  const switches = useStaffQuery<Switches>(eventId, "/participation-settings/");
  const command = useStaffCommand<CrewRow>(eventId), save = useStaffCommand<Switches>(eventId), reorder = useStaffCommand<CrewRow[]>(eventId);
  const [member, setMember] = useState(""), [role, setRole] = useState(""), [newKind, setNewKind] = useState<CrewKind | "">("");
  const toggle = (key: keyof Switches, value: boolean) =>
    save.mutate({ suffix: "/participation-settings/", method: "PATCH", body: { [key]: value } });
  const error = roster.error ?? command.error ?? save.error ?? reorder.error;
  const rows = roster.data ?? [];
  const waiting = rows.filter(row => row.state === "applied");
  const order = useCrewOrder(rows.filter(row => row.state === "approved"),
    ids => reorder.mutateAsync({ suffix: "/crew/reorder/", body: { ids } }));
  const card = (row: CrewRow, index?: number) => <CrewRowCard key={row.id} row={row} kinds={kinds} pending={command.isPending || reorder.isPending}
    onDecide={approve => command.mutate({ suffix: `/crew/${row.id}/decide/`, body: { approve, expected_version: row.version } })}
    onRemove={() => command.mutate({ suffix: `/crew/${row.id}/remove/` })}
    onSave={changes => command.mutate({ suffix: `/crew/${row.id}/`, method: "PATCH", body: { expected_version: row.version, ...changes } })}
    reorder={index === undefined || filtered ? undefined : order.handles(row, index)} />;
  return <section className="grid gap-4" aria-labelledby="crew-heading">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div className="grid gap-1">
        <h3 id="crew-heading" className="text-lg font-semibold text-ink">{t`Crew`}</h3>
        <p className="text-sm text-muted">{t`Crew places are free and never use the event's capacity.`}</p>
      </div>
      {kinds ? <label className="grid gap-1 text-sm font-semibold text-ink">{t`Show`}
        <select className="desk-input min-h-11" value={kind} onChange={e => setKind(e.target.value as CrewKind | "")}>
          <option value="">{t`Every kind`}</option>{CREW_KINDS.map(value => <option key={value} value={value}>{crewKindLabel(value)}</option>)}</select></label> : null}
    </header>
    {error ? <ErrorText message={error.message} /> : null}
    {switches.data ? <Card><fieldset className="grid gap-1">
      <legend className="text-sm font-semibold text-ink">{t`Sign-up link`}</legend>
      {([["crew_signup_open", t`Open the crew sign-up link`], ["crew_approval_required", t`Review each sign-up before approving`],
        ["crew_public_section", t`Show crew who opted in on the event page (public profiles only)`]] as const).map(([key, label]) =>
        <label key={key} className="flex min-h-11 items-center gap-3 text-sm text-ink">
          <input type="checkbox" checked={switches.data![key]} disabled={save.isPending} onChange={e => toggle(key, e.target.checked)} />{label}</label>)}
      {switches.data.crew_signup_open ? <p className="break-all text-sm text-muted">{t`Share: `}<a className="underline" href={signupUrl}>{signupUrl}</a></p> : null}
    </fieldset></Card> : null}
    {roster.isLoading ? <p role="status">{t`Loading crew…`}</p> : null}
    {roster.data?.length === 0 ? <p className="text-sm text-muted">{filtered ? t`Nobody of this kind is on the crew.` : t`Nobody is on the crew yet.`}</p> : null}
    {waiting.length ? <ul className="grid gap-2" aria-label={t`Waiting for review`}>{waiting.map(row => card(row))}</ul> : null}
    {order.rows.length ? <div className="grid gap-2">
      <p className="text-sm text-muted">{filtered ? t`Show every kind to change the order.` : t`This order is used on the roster and the public crew section. Drag a row, or use the arrows.`}</p>
      <ul className="grid gap-2" aria-label={t`On the crew`}>{order.rows.map((row, index) => card(row, index))}</ul>
      <p role="status" className="sr-only">{order.announcement}</p>
    </div> : null}
    <Card><form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault();
      command.mutate({ suffix: "/crew/", body: { member_id: Number(member), crew_role: role, ...(kinds && newKind ? { kind: newKind } : {}) } },
        { onSuccess: () => { setMember(""); setRole(""); setNewKind(""); } }); }}>
      <label className="grid gap-1 text-sm text-ink">{t`Account number`}<input className="desk-input" inputMode="numeric" required value={member} onChange={e => setMember(e.target.value.replace(/\D/g, ""))} /></label>
      <label className="grid gap-1 text-sm text-ink">{t`Role (optional)`}<input className="desk-input" maxLength={60} value={role} onChange={e => setRole(e.target.value)} placeholder={t`Door, AV, mentor`} /></label>
      {kinds ? <label className="grid gap-1 text-sm text-ink">{t`Kind (optional)`}<select className="desk-input" value={newKind} onChange={e => setNewKind(e.target.value as CrewKind | "")}>
        <option value="">{t`No kind`}</option>{CREW_KINDS.map(value => <option key={value} value={value}>{crewKindLabel(value)}</option>)}</select></label> : null}
      <button type="submit" className="desk-button" disabled={!member || command.isPending}>{t`Add to crew`}</button>
    </form></Card>
    {catering.data ? <Card><div className="grid gap-1">
      <p className="font-semibold text-ink">{t`Catering`}</p>
      <p className="text-sm text-muted">{t`${catering.data.approved} crew, ${catering.data.with_needs} with dietary needs.`}</p>
      <ul className="grid gap-1">{catering.data.needs.map(need => <li key={need.label} className="text-sm text-ink">{need.label}: {need.count}</li>)}</ul>
    </div></Card> : null}
  </section>;
}
