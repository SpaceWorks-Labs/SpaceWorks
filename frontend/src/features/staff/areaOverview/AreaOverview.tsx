import { t } from "@lingui/core/macro";
import { useContext, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";

import { Field, SegmentedControl } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { staffPathState, staffTabPath } from "../staffTabs";
import { TAB_LABELS } from "../staffTabLabels";
import { AllowedTabsContext } from "./allowedTabsContext";
import { AreaGroupList, TotalsLine } from "./AreaGroupList";
import { allGroupKeys, areaChoices, combine, filterAreas } from "./areaGrouping";
import { areaOverviewKeys, fetchAreaOverview, type AreaSection } from "./areaOverviewApi";

const RELATED = ["reports", "audit", "notifications"];

function intro(section: AreaSection) {
  return {
    finance: t`Money in and out for the areas you manage. Machines are split by type, then by machine. "Owed" is what people still have to pay today.`,
    tobuy: t`What to buy, by area. Machines are split by type, then by machine; inventory by item category.`,
    consumables: t`What gets used up, by area. Machines are split by type, then by machine; inventory by item category.`,
    repairs: t`Repairs, by area. Machines are split by type, then by machine; items by category; rooms by room.`,
    warranties: t`Warranty cover, by area. Machines are split by type; items by category.`,
  }[section];
}

function emptyText(section: AreaSection) {
  return {
    finance: t`No money moved in this range for the areas you manage, and nothing is owed.`,
    tobuy: t`Nothing to buy right now in the areas you manage.`,
    consumables: t`No consumables are tracked yet in the areas you manage.`,
    repairs: t`No open repairs in the areas you manage.`,
    warranties: t`No equipment with warranty cover in the areas you manage.`,
  }[section];
}

function isoDay(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/** Links to this area's reports, audit log and inbox: only tabs this person can already open. */
function RelatedLinks() {
  const allowed = useContext(AllowedTabsContext);
  const location = useLocation();
  const tabs = RELATED.filter(tab => allowed.includes(tab));
  if (!tabs.length) return null;
  const slug = staffPathState(location.pathname, false).makerspaceSlug || null;
  return <nav aria-label={t`More for your area`} className="flex flex-wrap items-center gap-3 text-sm">
    <span className="text-muted">{t`More for your area:`}</span>
    {tabs.map(tab => <Link key={tab} className="font-semibold underline" to={consoleSessionHref(staffTabPath(tab, false, slug))}>
      {TAB_LABELS[tab] ?? tab}</Link>)}
  </nav>;
}

/**
 * One area list grouped the way each manager thinks about it (decision 241): by area, then
 * machine type and machine, or item category. The server returns only the caller's own rows
 * (an area manager their area, the Space Manager every area); this filters by area, folds
 * groups open and closed, and shows each group's totals.
 */
export function AreaOverview({ makerspaceId, section }: { makerspaceId: number; section: AreaSection }) {
  const today = new Date();
  const [from, setFrom] = useState(isoDay(new Date(today.getFullYear(), today.getMonth() - 11, 1)));
  const [to, setTo] = useState(isoDay(today));
  const [area, setArea] = useState("");
  const [showDone, setShowDone] = useState(false);
  const [open, setOpen] = useState<Set<string> | null>(null);
  const params = new URLSearchParams();
  if (section === "finance") { params.set("from", from); params.set("to", to); }
  if ((section === "tobuy" || section === "repairs") && showDone) params.set("status", "all");
  const query = useQuery({ queryKey: areaOverviewKeys.section(makerspaceId, section, params.toString()),
    queryFn: () => fetchAreaOverview(makerspaceId, section, params), retry: false });
  const groups = useMemo(() => filterAreas(query.data?.groups ?? [], area ? [area] : []), [query.data, area]);
  const expanded = open ?? new Set(groups.map(group => `/${group.key}`));
  const toggle = (path: string) => setOpen(() => {
    const next = new Set(expanded);
    if (next.has(path)) next.delete(path); else next.add(path);
    return next;
  });
  const totals = combine(groups);
  const areas = query.data?.areas ?? [];
  const denied = query.error instanceof StructuredApiError && [403, 404].includes(query.error.status);
  return <section className="grid min-w-0 gap-4" aria-label={t`Grouped by area`}>
    <p className="text-sm text-muted">{intro(section)}</p>
    <div className="flex flex-wrap items-end gap-3">
      {section === "finance" ? <>
        <Field label={t`From`}><input type="date" className="desk-input" value={from} max={to} onChange={event => setFrom(event.target.value)} /></Field>
        <Field label={t`To`}><input type="date" className="desk-input" value={to} min={from} onChange={event => setTo(event.target.value)} /></Field>
      </> : null}
      {areas.length > 1 ? <SegmentedControl label={t`Area`} value={area || "all"}
        options={[{ value: "all", label: t`All areas` }, ...areaChoices(areas)]} onChange={value => setArea(value === "all" ? "" : value)} /> : null}
      {section === "tobuy" || section === "repairs" ? <label className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" checked={showDone} onChange={event => setShowDone(event.target.checked)} />
        {section === "tobuy" ? t`Include bought and cancelled` : t`Include fixed and closed`}</label> : null}
      {groups.length ? <div className="ml-auto flex gap-2">
        <button type="button" className="desk-button" onClick={() => setOpen(new Set(allGroupKeys(groups)))}>{t`Open all`}</button>
        <button type="button" className="desk-button" onClick={() => setOpen(new Set())}>{t`Close all`}</button>
      </div> : null}
    </div>
    {query.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading…`}</p> : null}
    {query.error ? <p role="alert" className="text-sm text-danger">{denied
      ? t`This list is not switched on for the areas you manage.`
      : query.error instanceof Error ? query.error.message : t`Something went wrong. Try again.`}</p> : null}
    {query.data && !groups.length ? <p className="rounded-lg border border-line bg-panel p-4 text-sm text-muted">{emptyText(section)}</p> : null}
    {groups.length ? <>
      <p className="flex flex-wrap gap-x-3 text-sm" aria-live="polite">
        <strong>{area ? t`This area` : t`All your areas`}</strong>
        <span className="tabular-nums"><TotalsLine section={section} finance={totals.finance} money={totals.money} /></span>
      </p>
      <AreaGroupList section={section} groups={groups} open={expanded} onToggle={toggle} />
    </> : null}
    {query.data?.truncated ? <p className="text-sm text-muted">{t`Only the first 500 rows are listed; the totals count every row.`}</p> : null}
    <RelatedLinks />
  </section>;
}
