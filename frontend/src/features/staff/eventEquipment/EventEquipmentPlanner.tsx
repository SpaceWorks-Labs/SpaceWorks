import { plural, t } from "@lingui/core/macro";
import { useContext, useState } from "react";

import { capabilityOn } from "../../../lib/features";
import { StaffListContext } from "../StaffListContext";
import { eventErrorText } from "../eventUi";
import { EventsOnlyBadge } from "./EventsOnlyBadge";
import { EventReturnWindowField } from "./EventReturnWindowField";
import { PlanPreview, PlanResults, WindowSummary, windowCounts, windowStatusPill } from "./EventEquipmentPlanParts";
import { useEquipmentPicker, useEquipmentPlan, useWindowAvailability, type PlanBody, type PlanResponse } from "./eventEquipmentApi";
import { PersonLinesOverride, personLines, type LineOverrides } from "./EventEquipmentPersonLines";
import { EventPanelPager } from "../EventPanelPager";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";

type Participant = { id: number; name: string; status: string };
type Props = { makerspaceId: number; eventId: number; participants: Participant[]; canEditWindow: boolean };

/**
 * Decision 221b: plan equipment for several registered people at once. One ordinary pending
 * request is created per person, so every issue still records one accountable borrower; the
 * window figures come from the inventory availability owner and reserve nothing.
 */
export function EventEquipmentPlanner(props: Props) {
  const { makerspace } = useContext(StaffListContext);
  const modules = makerspace?.enabled_modules ?? [];
  if (makerspace?.id !== props.makerspaceId || !modules.includes("events") || !modules.includes("request_workflow")
    || !capabilityOn(makerspace, "loans.enabled")) return null;
  return <Planner key={props.eventId} {...props} />;
}

function Planner({ makerspaceId, eventId, participants, canEditWindow }: Props) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [lines, setLines] = useState<Record<number, { name: string; quantity: number }>>({});
  const [people, setPeople] = useState<number[]>([]);
  const [overrides, setOverrides] = useState<LineOverrides>({});
  const [purpose, setPurpose] = useState("");
  const [preview, setPreview] = useState<PlanResponse | null>(null);
  const [operation, setOperation] = useState<string | null>(null);
  const picker = useEquipmentPicker(makerspaceId, eventId, page, open);
  const rows = picker.data?.results ?? [];
  const windowQuery = useWindowAvailability(makerspaceId, eventId, open ? rows.map((row) => row.id) : []);
  const plan = useEquipmentPlan(makerspaceId, eventId);
  const eligible = participants.filter((row) => ["registered", "attended"].includes(row.status));
  const names = Object.fromEntries(Object.entries(lines).map(([id, line]) => [id, line.name]));
  const personNames = Object.fromEntries(participants.map((row) => [row.id, row.name]));
  const chosen = Object.keys(lines).length;
  const results = plan.data && !plan.data.dry_run ? plan.data.results : null;
  const changed = () => { setPreview(null); setOperation(null); plan.reset(); };
  const body = (dryRun: boolean, operationId: string): PlanBody => ({
    operation_id: operationId, requested_for: purpose.trim(), dry_run: dryRun,
    lines: Object.entries(lines).map(([id, line]) => ({ product_id: Number(id), quantity: line.quantity })),
    participants: people.map((registration_id) => {
      const own = personLines(lines, overrides[registration_id]);
      return own ? { registration_id, lines: own } : { registration_id };
    }),
  });
  const emptyOverride = people.some((id) => personLines(lines, overrides[id])?.length === 0);
  const reset = () => { changed(); setLines({}); setPeople([]); setPurpose(""); setOverrides({}); };

  if (!open) return <button className="desk-button w-fit" type="button" aria-expanded={false} onClick={() => setOpen(true)}>{t`Plan equipment for several people`}</button>;
  return <section className="grid gap-4 rounded-xl border border-line bg-panel p-4" aria-labelledby={`equipment-plan-${eventId}`} data-replay-block>
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div><h4 id={`equipment-plan-${eventId}`} className="title-section">{t`Plan equipment`}</h4>
        <p className="text-sm text-muted">{t`Each chosen person gets their own request for review, so every item stays with one accountable borrower.`}</p></div>
      <button className="desk-button-ghost" type="button" aria-expanded onClick={() => setOpen(false)}>{t`Close planner`}</button>
    </div>
    {windowQuery.data ? <WindowSummary data={windowQuery.data} /> : null}
    {canEditWindow && windowQuery.data ? <EventReturnWindowField makerspaceId={makerspaceId} eventId={eventId} hours={windowQuery.data.equipment_return_hours} /> : null}
    <fieldset className="grid min-w-0 gap-2" disabled={plan.isPending}>
      <legend className="mb-1 text-sm font-semibold text-ink">{t`Equipment`}</legend>
      {picker.isPending ? <LogoLoader label={t`Loading equipment…`} size={48} className="min-h-16 py-3" /> : null}
      {picker.isError ? <p className="text-sm text-danger" role="alert">{t`Equipment is unavailable for your access.`}</p> : null}
      {picker.isSuccess && !rows.length ? <p className="text-sm text-muted">{t`No requestable equipment is listed for this event.`}</p> : null}
      {windowQuery.isError ? <p className="text-sm text-muted">{t`Availability for the event window could not be checked.`}</p> : null}
      <ul className="grid gap-2">{rows.map((row) => {
        const figure = windowQuery.data?.results.find((item) => item.product_id === row.id);
        const line = lines[row.id];
        return <li key={row.id} className="flex flex-wrap items-center gap-2">
          <label className="flex min-h-11 min-w-0 items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(line)} onChange={(event) => {
            changed();
            setLines((current) => { const next = { ...current }; if (event.target.checked) next[row.id] = { name: row.name, quantity: 1 }; else delete next[row.id]; return next; });
          }} /><span className="[overflow-wrap:anywhere]">{row.name}</span></label>
          {row.event_only || figure?.event_only ? <EventsOnlyBadge /> : null}
          {figure ? windowStatusPill(figure) : null}
          {figure && windowCounts(figure) ? <span className="text-sm tabular-nums text-muted">{windowCounts(figure)}</span> : null}
          {line ? <label className="flex items-center gap-1 text-sm">{t`Each`}<input className="desk-input w-20" type="number" min={1} max={99} value={line.quantity}
            aria-label={t`Quantity of ${row.name} per person`} onChange={(event) => {
              const quantity = Math.min(99, Math.max(1, Math.trunc(Number(event.target.value) || 1)));
              changed(); setLines((current) => ({ ...current, [row.id]: { ...line, quantity } }));
            }} /></label> : null}
        </li>;
      })}</ul>
      <EventPanelPager page={page} setPage={setPage} next={picker.data?.next} />
    </fieldset>
    <fieldset className="grid min-w-0 gap-1" disabled={plan.isPending}>
      <legend className="mb-1 text-sm font-semibold text-ink">{t`People on this page`}</legend>
      {!eligible.length ? <p className="text-sm text-muted">{t`No registered or attended people on this page of the roster.`}</p> : <>
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={people.length === eligible.length}
          onChange={(event) => { changed(); setPeople(event.target.checked ? eligible.map((row) => row.id) : []); }} />{t`Everyone listed`}</label>
        {eligible.map((row) => <div key={row.id} className="grid">
          <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={people.includes(row.id)}
            onChange={(event) => { changed(); setPeople((ids) => event.target.checked ? [...ids, row.id] : ids.filter((id) => id !== row.id)); }} />
            <span className="[overflow-wrap:anywhere]">{row.name}</span></label>
          {people.includes(row.id) ? <PersonLinesOverride person={row.name} defaults={lines} value={overrides[row.id]} onChange={(next) => {
            changed(); setOverrides((current) => { const copy = { ...current }; if (next) copy[row.id] = next; else delete copy[row.id]; return copy; });
          }} /> : null}
        </div>)}
      </>}
    </fieldset>
    <label className="grid gap-1 text-sm">{t`Purpose`}<input className="desk-input" maxLength={500} value={purpose} disabled={plan.isPending}
      onChange={(event) => { changed(); setPurpose(event.target.value); }} /></label>
    {preview ? <PlanPreview preview={preview} names={names} /> : null}
    {results ? <PlanResults results={results} people={personNames} /> : null}
    {plan.error ? <p className="text-sm text-danger" role="alert">{eventErrorText(plan.error)}</p> : null}
    <div className="flex flex-wrap gap-2">
      {results ? <>
        {results.some((row) => row.outcome === "error") ? <button className="desk-button" type="button" disabled={plan.isPending}
          onClick={() => operation && plan.mutate(body(false, operation))}>{plan.isPending ? <><BoxArt size={16} mono />{t`Retrying…`}</> : t`Retry failed`}</button> : null}
        <button className="desk-button" type="button" disabled={plan.isPending} onClick={reset}>{t`Plan more`}</button>
      </> : preview ? <>
        <button className="desk-button-primary" type="button" disabled={plan.isPending} onClick={() => {
          const id = operation ?? crypto.randomUUID(); setOperation(id); plan.mutate(body(false, id));
        }}>{plan.isPending ? <><BoxArt size={16} mono />{t`Creating requests…`}</> : plural(people.length, { one: "Create # request", other: "Create # requests" })}</button>
        <button className="desk-button" type="button" disabled={plan.isPending} onClick={changed}>{t`Change plan`}</button>
      </> : <button className="desk-button" type="button" disabled={plan.isPending || !chosen || !people.length || chosen > 20 || emptyOverride}
        onClick={() => plan.mutate(body(true, crypto.randomUUID()), { onSuccess: setPreview })}>{plan.isPending ? <><BoxArt size={16} mono />{t`Checking…`}</> : t`Preview plan`}</button>}
    </div>
  </section>;
}
