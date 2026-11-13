import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useUrlListState } from "../../lib/useUrlListState";
import { SavedViewsMenu } from "../staff/SavedViewsMenu";
import { useSearchParams } from "react-router-dom";

import { ListLayout } from "../../components/layouts";
import { ListRow, StatusPill } from "../../components/ui";
import { formatDate } from "../../lib/format";
import type { Makerspace } from "../staff/panels/shared";
import {
  AREA_LABELS, incidentErrorMessage, KIND_LABELS, options, SEVERITY_LABELS, severityTone, STATUS_LABELS, statusTone,
  SUBJECT_FILTERS, useIncidents, type Incident, type IncidentFilters, type IncidentSubjectFilter,
} from "./api";
import { IncidentDetail } from "./IncidentDetail";
import { RecordIncidentDialog } from "./RecordIncidentDialog";

const NO_FILTERS: IncidentFilters = { status: "", severity: "", area: "", kind: "" };
const SUBJECT_LABELS: Record<(typeof SUBJECT_FILTERS)[number], string> = {
  machine: t`machine`, event: t`event`, booking: t`booking`, room: t`room`, loan: t`loan`, product: t`item`, person: t`person`,
};

/** A cross-link (`?machine=12` from the machine drawer, `?event=` from an event…) narrows the register to that record. */
function subjectFromParams(params: URLSearchParams): IncidentSubjectFilter {
  for (const key of SUBJECT_FILTERS) {
    const id = Number(params.get(key));
    if (Number.isInteger(id) && id > 0) return { key, id };
  }
  return null;
}

/** The staff incident register (decision 223 (k)). The server narrows every row to the
 *  reader's areas; the Space Manager reads them all. Opening a row keeps `?incident=` in the URL. */
export function IncidentRegister({ makerspace }: { makerspace: Pick<Makerspace, "id"> }) {
  const [params, setParams] = useSearchParams();
  // Filters live in the URL so a saved view (MC10) and Back/Forward restore them.
  const list = useUrlListState({ ...NO_FILTERS, page: "1" });
  const filters: IncidentFilters = { status: list.values.status, severity: list.values.severity, area: list.values.area, kind: list.values.kind };
  const page = list.page;
  const setPage = (next: number) => list.setPage(next);
  const setFilters = (next: IncidentFilters) => list.update({ ...next });
  const [recording, setRecording] = useState(false);
  const subject = subjectFromParams(params);
  const query = useIncidents(makerspace.id, filters, page, subject);
  // Rows are re-checked against the linked record, so a server without the filter never lists unrelated incidents.
  const rows = (query.data?.results ?? []).filter(row => !subject || !(subject.key in row) || Number(row[subject.key as keyof Incident]) === subject.id);
  const open = (id: number | null) => setParams(current => {
    const next = new URLSearchParams(current);
    if (id === null) next.delete("incident"); else next.set("incident", String(id));
    return next;
  });
  const incidentId = Number(params.get("incident")) || null;
  if (incidentId) return <IncidentDetail id={incidentId} onBack={() => open(null)} />;
  const filtered = Object.values(filters).some(Boolean) || Boolean(subject);
  const clearSubject = () => setParams(current => {
    const next = new URLSearchParams(current);
    SUBJECT_FILTERS.forEach(key => next.delete(key));
    return next;
  });
  const choose = (key: keyof IncidentFilters, value: string) => list.setFilter(key, value);
  const select = (key: keyof IncidentFilters, label: string, all: string, choices: { value: string; label: string }[]) =>
    <label className="grid min-w-0 gap-1 text-sm font-semibold">{label}
      <select className="desk-input" value={filters[key]} onChange={event => choose(key, event.target.value)}>
        <option value="">{all}</option>
        {choices.map(row => <option key={row.value} value={row.value}>{row.label}</option>)}
      </select></label>;
  return <>
    <ListLayout header={{ title: t`Incidents`, subtitle: t`Safety incidents and near misses, from report to resolution.`,
      primary: { label: t`Record incident`, icon: "Plus", onClick: () => setRecording(true) } }}
      filters={{ toolbar: <div className="grid min-w-0 grid-cols-2 gap-3 lg:grid-cols-4" role="group" aria-label={t`Filter incidents`}>
        {select("status", t`Status`, t`Any status`, options(STATUS_LABELS))}
        {select("severity", t`Severity`, t`Any severity`, options(SEVERITY_LABELS))}
        {select("area", t`Area`, t`Any area`, options(AREA_LABELS))}
        {select("kind", t`Kind`, t`Incidents and near misses`, options(KIND_LABELS))}
        <div className="col-span-2 lg:col-span-4"><SavedViewsMenu makerspaceId={makerspace.id} entity="incidents" state={list.values} onRestore={list.restore} /></div>
        {subject ? <p className="col-span-2 flex flex-wrap items-center gap-2 text-sm lg:col-span-4">
          <span>{t`Showing incidents linked to ${SUBJECT_LABELS[subject.key]} #${subject.id}.`}</span>
          <button type="button" className="desk-button" onClick={clearSubject}>{t`Show all incidents`}</button>
        </p> : null}
      </div> }}
      state={query.isLoading ? { status: "loading" } : query.error
        ? { status: "error", error: incidentErrorMessage(query.error), onRetry: () => { void query.refetch(); } } : { status: "ready" }}
      isEmpty={!rows.length} filtered={filtered}
      empty={{ message: t`No incidents recorded. Reports from members and staff land here.` }}
      filteredEmpty={{ message: t`No incidents match these filters.`, action: { label: t`Clear filters`, onClick: () => { setFilters(NO_FILTERS); clearSubject(); } } }}
      pagination={query.data && query.data.count > 24 ? { page, pageSize: 24, count: query.data.count, onChange: setPage } : undefined}
      body={{ kind: "rows", rows: rows.map(row => <IncidentRow key={row.id} incident={row} onOpen={() => open(row.id)} />) }} />
    {recording ? <RecordIncidentDialog makerspaceId={makerspace.id} onClose={() => setRecording(false)} onRecorded={row => open(row.id)} /> : null}
  </>;
}

function IncidentRow({ incident, onOpen }: { incident: Incident; onOpen: () => void }) {
  const openActions = incident.actions.filter(action => !action.done_at).length;
  return <ListRow title={incident.title} onClick={onOpen}
    identity={{ kind: "icon", icon: incident.kind === "near_miss" ? "ShieldAlert" : "TriangleAlert", tone: severityTone(incident.severity) }}
    meta={[KIND_LABELS[incident.kind], AREA_LABELS[incident.area], formatDate(incident.occurred_at),
      openActions ? t`${openActions} open follow-ups` : ""].filter(Boolean).join(" · ")}
    right={<span className="flex flex-wrap gap-1.5">
      <StatusPill tone={statusTone(incident.status)} label={STATUS_LABELS[incident.status]} />
      <StatusPill tone={severityTone(incident.severity)} label={SEVERITY_LABELS[incident.severity]} />
    </span>} />;
}
