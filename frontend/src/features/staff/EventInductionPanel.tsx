import { LogoLoader } from "../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useContext, useState } from "react";

import { StructuredApiError } from "../../lib/api";
import { StaffListContext } from "./StaffListContext";
import { certificationKeys, getCertificationTypes } from "./certificationsApi";
import { inductionErrorText, inductionResultText, useInduction, useInductionActions, type InductionResult } from "./eventInductionApi";
import type { StaffEvent } from "./eventsApi";
import { BoxArt } from "../../components/BoxSpinner";

/**
 * `canLinkEvent` is the event's own authority (`can_manage_staff`: Event Manager, organizer or
 * co-organizer). Decision 224(b): marking an event as an induction needs it as well as machine
 * authority, because a link exposes the event's checked-in attendees.
 */
type Props = { makerspaceId: number; event: Pick<StaffEvent, "id" | "status" | "starts_at">; enabledFeatures: readonly string[]; enabledModules: readonly string[];
  active?: boolean; canLinkEvent?: boolean };

/**
 * Decision 223 (k) P1: mark an event as an induction for a machine certification, then grant it
 * to the attendees who checked in -- one audited grant each, with a result per person. Needs
 * `machines.induction_events` (machines + events) and machine-management authority.
 */
export function EventInductionPanel(props: Props) {
  const { actions, isSuperadmin } = useContext(StaffListContext);
  const on = props.enabledFeatures.includes("machines.induction_events") && props.enabledModules.includes("machines")
    && props.enabledModules.includes("events") && (isSuperadmin || actions?.includes("manage_machines"));
  return on ? <Induction {...props} /> : null;
}

function errorText(error: unknown, linking = false) {
  if (!error) return "";
  if (linking && error instanceof StructuredApiError && error.status === 403) return t`Linking an induction also needs access to this event.`;
  const code = error instanceof StructuredApiError ? error.code : undefined;
  return inductionErrorText(code) || (error instanceof Error ? error.message : t`That did not work. Try again.`);
}

function Induction({ makerspaceId, event, active = true, canLinkEvent = false }: Props) {
  const overview = useInduction(makerspaceId, event.id, active);
  const types = useQuery({ queryKey: certificationKeys.types(makerspaceId), enabled: active, queryFn: () => getCertificationTypes(makerspaceId) });
  const { link, unlink, grant, revoke } = useInductionActions(makerspaceId, event.id);
  const [typeId, setTypeId] = useState(0);
  const [chosen, setChosen] = useState<number[]>([]);
  const [results, setResults] = useState<InductionResult[]>([]);
  if (overview.isPending) return <LogoLoader label={t`Loading induction…`} />;
  if (overview.isError) return null; // 404: switched off or not a machine manager for this space.
  const data = overview.data;
  const linkedIds = new Set(data.links.map(row => row.certification_type));
  const choices = (types.data ?? []).filter(row => row.is_active && !linkedIds.has(row.id));
  const started = new Date(event.starts_at).getTime() <= Date.now() && event.status !== "draft" && event.status !== "cancelled";
  const typeName = (id: number) => data.links.find(row => row.certification_type === id)?.certification_type_name ?? `#${id}`;
  const personName = (id: number) => data.attendees.find(row => row.user_id === id)?.name ?? `#${id}`;
  const toggle = (id: number, on: boolean) => setChosen(rows => on ? [...rows, id] : rows.filter(row => row !== id));
  const error = link.error || unlink.error || grant.error || revoke.error;
  return <section aria-labelledby={`induction-${event.id}`} className="grid gap-3 rounded-lg border border-line p-3 text-sm">
    <div>
      <h3 id={`induction-${event.id}`} className="title-section">{t`Induction`}</h3>
      <p className="text-muted">{t`An induction lets you certify the attendees who checked in, in one step. Nothing is granted until you press Grant.`}</p>
    </div>
    {data.links.length ? <ul className="grid gap-2" aria-label={t`Certifications this event inducts`}>
      {data.links.map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-2">
        <span>{row.certification_type_name}</span>
        <button type="button" className="desk-button-ghost min-h-11" disabled={unlink.isPending} onClick={() => unlink.mutate(row.id)}>{t`Remove ${row.certification_type_name}`}</button>
      </li>)}
    </ul> : <p>{t`This event is not an induction yet.`}</p>}
    {event.status !== "cancelled" && !canLinkEvent ? <p className="text-muted">{t`Linking an induction also needs access to this event.`}</p> : null}
    {event.status !== "cancelled" && canLinkEvent ? <div className="flex flex-wrap items-end gap-2">
      <label className="grid gap-1">{t`Certification`}
        <select className="desk-input" value={typeId} onChange={change => setTypeId(Number(change.target.value))}>
          <option value={0}>{types.isPending ? t`Loading certifications…` : t`Choose a certification`}</option>
          {choices.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select></label>
      <button type="button" className="desk-button" disabled={!typeId || link.isPending} onClick={() => link.mutate(typeId, { onSuccess: () => setTypeId(0) })}>{t`Mark as induction`}</button>
    </div> : null}
    {data.links.length ? <fieldset className="grid gap-2" disabled={grant.isPending}>
      <legend className="font-semibold text-ink">{t`Checked-in attendees`}</legend>
      {!started ? <p className="text-muted">{t`Grant certifications once the event has started and attendees have checked in.`}</p> : null}
      {!data.attendees.length ? <p className="text-muted">{t`No one has checked in yet.`}</p> : null}
      {data.attendees.map(person => {
        const done = data.links.every(row => person.certified_type_ids.includes(row.certification_type));
        return <label key={person.user_id} className="flex min-h-11 items-start gap-2">
          <input type="checkbox" className="mt-1 h-4 w-4" checked={chosen.includes(person.user_id)} disabled={done}
            onChange={change => toggle(person.user_id, change.target.checked)} />
          <span>{person.name}{person.is_member ? "" : ` · ${t`guest`}`}{done ? ` · ${t`already certified`}` : ""}</span>
        </label>;
      })}
      {data.attendees.length ? <button type="button" className="desk-button-primary w-full sm:w-fit" disabled={!chosen.length || !data.can_grant || !started}
        onClick={() => grant.mutate({ user_ids: chosen }, { onSuccess: response => { setResults(response.results); setChosen([]); } })}>
        {grant.isPending ? <><BoxArt size={16} mono />{t`Granting…`}</> : t`Grant certification to ${chosen.length} selected`}</button> : null}
    </fieldset> : null}
    {results.length ? <ul className="grid gap-1" aria-label={t`Grant results`} role="status">
      {results.map(row => <li key={`${row.user_id}:${row.certification_type_id}`} className="flex flex-wrap items-center gap-2">
        <span className={row.status === "refused" ? "text-danger" : undefined}>{personName(row.user_id)} · {typeName(row.certification_type_id)}: {inductionResultText(row)}</span>
        {row.status === "granted" && row.guest && row.grant_id ? <button type="button" className="desk-button-ghost min-h-11" disabled={revoke.isPending}
          onClick={() => revoke.mutate(row.grant_id as number, { onSuccess: () => setResults(rows => rows.filter(item => item !== row)) })}>{t`Revoke`}</button> : null}
      </li>)}
    </ul> : null}
    {error ? <p role="alert" className="text-danger">{errorText(error, error === link.error)}</p> : null}
  </section>;
}
