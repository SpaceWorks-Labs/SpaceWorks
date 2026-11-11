import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorText, Field } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { useTechnicians } from "./techniciansApi";

export type Area = "machines" | "inventory" | "rooms";
export type TechnicianDefault = { id: number; area: Area; machine_type_id: number | null; room_id: number | null; contact_id: number };

const AREA_LABELS: Record<Area, string> = { machines: t`Machines`, inventory: t`Inventory`, rooms: t`Rooms` };
const path = (id: number) => `/admin/makerspaces/${id}/technician-defaults`;

/**
 * Technicians pre-ticked when a repair job is dispatched: for a whole area, or narrowed to a
 * machine type or room the technician covers. Each area's manager sets its own defaults;
 * the server refuses an area the caller does not manage.
 */
export function TechnicianDefaults({ makerspaceId, areas }: { makerspaceId: number; areas: Area[] }) {
  const client = useQueryClient();
  const key = ["technician-defaults", makerspaceId] as const;
  const defaults = useQuery({ queryKey: key, queryFn: () => staffRequest<TechnicianDefault[]>(path(makerspaceId)) });
  const technicians = useTechnicians(makerspaceId);
  const [form, setForm] = useState({ area: areas[0] ?? "machines", contact: "", narrow: "" });
  const change = useMutation({
    mutationFn: ({ row, remove }: { row: Omit<TechnicianDefault, "id">; remove: boolean }) =>
      staffRequest<TechnicianDefault[]>(`${path(makerspaceId)}${remove ? "?remove=true" : ""}`, { method: "POST", body: JSON.stringify(row) }),
    onSuccess: data => { client.setQueryData(key, data); setForm(current => ({ ...current, contact: "", narrow: "" })); },
  });
  const people = (technicians.data ?? []).filter(row => !row.is_archived);
  const name = (id: number) => people.find(row => row.id === id)?.name ?? t`Technician ${id}`;
  const contact = people.find(row => String(row.id) === form.contact);
  const kind = form.area === "machines" ? "machine_type" : form.area === "rooms" ? "room" : null;
  const narrowOptions = kind ? (contact?.coverage ?? []).filter(row => row.kind === kind && row.id !== null) : [];
  const label = (row: TechnicianDefault) => {
    const id = row.machine_type_id ?? row.room_id;
    const owner = people.flatMap(person => person.coverage).find(item => item.id === id
      && item.kind === (row.machine_type_id ? "machine_type" : "room"));
    return id === null ? t`Whole area` : owner?.label ?? (row.machine_type_id ? t`Machine type ${id}` : t`Room ${id}`);
  };
  const submit = () => change.mutate({ remove: false, row: { area: form.area, contact_id: Number(form.contact),
    machine_type_id: form.area === "machines" && form.narrow ? Number(form.narrow) : null,
    room_id: form.area === "rooms" && form.narrow ? Number(form.narrow) : null } });
  return <section className="grid gap-3 rounded-lg border border-line p-3" aria-labelledby="technician-defaults-title">
    <div><h3 id="technician-defaults-title" className="title-section">{t`Pre-ticked technicians`}</h3>
      <p className="text-sm text-muted">{t`Who is ticked by default when you send a repair job. You can still change it on each job.`}</p></div>
    {defaults.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading defaults…`}</p> : null}
    {defaults.error ? <ErrorText message={defaults.error.message} /> : null}
    {defaults.data && !defaults.data.length ? <p className="text-sm text-muted">{t`No defaults yet.`}</p> : null}
    <ul className="grid gap-2">
      {(defaults.data ?? []).map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-panel p-2">
        <span className="text-sm">{name(row.contact_id)} · {AREA_LABELS[row.area]} · {label(row)}</span>
        {areas.includes(row.area) ? <button type="button" className="desk-button-ghost" disabled={change.isPending}
          onClick={() => change.mutate({ remove: true, row: { area: row.area, contact_id: row.contact_id, machine_type_id: row.machine_type_id, room_id: row.room_id } })}>
          {t`Remove`}</button> : null}
      </li>)}
    </ul>
    {areas.length ? <form className="grid gap-3 sm:grid-cols-[repeat(3,minmax(0,1fr))_auto] sm:items-end" onSubmit={event => { event.preventDefault(); if (form.contact) submit(); }}>
      <Field label={t`Area`}><select className="desk-input" value={form.area} onChange={event => setForm({ area: event.target.value as Area, contact: form.contact, narrow: "" })}>
        {areas.map(area => <option key={area} value={area}>{AREA_LABELS[area]}</option>)}</select></Field>
      <Field label={t`Technician`}><select className="desk-input" value={form.contact} onChange={event => setForm({ ...form, contact: event.target.value, narrow: "" })}>
        <option value="">{t`Choose a technician`}</option>
        {people.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
      <Field label={t`Only for`} hint={kind ? t`From what this technician covers.` : undefined}>
        <select className="desk-input" value={form.narrow} disabled={!narrowOptions.length} onChange={event => setForm({ ...form, narrow: event.target.value })}>
          <option value="">{t`Whole area`}</option>
          {narrowOptions.map(row => <option key={`${row.kind}-${row.id}`} value={String(row.id)}>{row.label ?? String(row.id)}</option>)}</select></Field>
      <button type="submit" className="desk-button" disabled={!form.contact || change.isPending}>{t`Add default`}</button>
    </form> : null}
    {change.error ? <ErrorText message={change.error.message} /> : null}
  </section>;
}
