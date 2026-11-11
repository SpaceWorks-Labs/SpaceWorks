import { t } from "@lingui/core/macro";
import { useContext, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { ListLayout } from "../../../components/layouts";
import { ErrorText, Field, ListRow, Modal, StatusBadge, StatusPill } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import { inventoryQueryState } from "./inventoryPresentation";
import { type Makerspace, useStaffGet } from "./shared";
import { LinkedConsumableUse } from "./LinkedConsumableUse";
import { useLinkedUseOwners } from "./useLinkedUseOwners";
import { StaffListContext } from "../StaffListContext";
import { staffTabPath } from "../staffTabs";
import { capabilityOn } from "../../../lib/features";
import { AreaOverviewPage } from "../areaOverview/AreaOverviewPage";
import { PlannedShortages } from "./PlannedShortages";
import {
  CONSUMABLES_PAGE_SIZE, SOURCE_LABELS, SOURCE_TONES, consumableKeys, consumablesPath, logConsumableUse, unitLabel,
  type ConsumablePage, type ConsumableRow, type ConsumableStatus,
} from "./consumablesApi";

const STATUSES: { key: ConsumableStatus; label: string }[] = [
  { key: "all", label: t`All` }, { key: "low", label: t`Running low` }, { key: "ok", label: t`Stocked` },
];

/** Everything the space uses up, in one list: item consumables, per-machine consumables and material pools. */
export function ConsumablesPanel({ makerspace, canEditInventory = false }: { makerspace: Makerspace; canEditInventory?: boolean }) {
  const [params, setParams] = useSearchParams();
  const raw = params.get("status");
  const status: ConsumableStatus = raw === "low" || raw === "ok" ? raw : "all";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [usingRow, setUsingRow] = useState<ConsumableRow | null>(null);
  const access = useContext(StaffListContext);
  const latestAccess = useRef(access); latestAccess.current = access;
  const canReviewAudit = () => Boolean(latestAccess.current.isSuperadmin || latestAccess.current.actions?.includes("view_audit"));
  const linked = useLinkedUseOwners(makerspace.id);
  const query = useStaffGet<ConsumablePage>([...consumableKeys.list(makerspace.id, status, page)], consumablesPath(makerspace.id, status, page));
  const rows = query.data?.results ?? [];
  const href = (next: ConsumableStatus) => { const search = new URLSearchParams(params); search.set("status", next); search.delete("page"); return `?${search}`; };
  const toBuyHref = `/m/${makerspace.slug}/admin/to-buy?status=all`;
  const showView = (view: string) => setParams(current => { const next = new URLSearchParams(current); if (view) next.set("view", view); else next.delete("view"); return next; });
  // Decision 241: grouped by area, machine type then machine, and item category.
  if (params.get("view") === "groups") return <AreaOverviewPage title={t`Consumables, grouped`} makerspaceId={makerspace.id} section="consumables" onBack={() => showView("")} />;
  // C25: upcoming events/bookings whose planned use outruns stock, only while one of those areas is on.
  const modules = makerspace.enabled_modules ?? [];
  const planned = ["events", "bookings"].some(module => modules.includes(module))
    ? <PlannedShortages makerspaceId={makerspace.id} slug={makerspace.slug} enabledModules={modules} /> : undefined;
  return <ListLayout header={{ title: t`Consumables`, subtitle: t`What the space uses up, and what is running low.`,
    overflow: [{ label: t`Group by area and machine`, onClick: () => showView("groups") }] }}
    tabs={STATUSES.map(option => ({ key: option.key, label: option.label, href: href(option.key) }))} activeTab={status}
    state={inventoryQueryState(query, "consumables")} isEmpty={!rows.length} filtered={status !== "all"}
    empty={{ message: t`No consumables yet. Mark a quantity-tracked item as a consumable in its details.` }}
    filteredEmpty={{ message: status === "low" ? t`Nothing is running low.` : t`Nothing is fully stocked right now.`, action: { label: t`View all`, href: href("all") } }}
    body={{ kind: "rows", rows: rows.map(row => <ConsumableListRow key={`${row.source}-${row.id}`} row={row} toBuyHref={toBuyHref}
      onUse={row.source === "item" && canEditInventory ? () => setUsingRow(row) : undefined} />) }}
    pagination={query.data && query.data.count > CONSUMABLES_PAGE_SIZE ? { page, pageSize: CONSUMABLES_PAGE_SIZE, count: query.data.count,
      onChange: next => setParams(current => { const search = new URLSearchParams(current); search.set("page", String(next)); return search; }) } : undefined}
    rail={planned}
    detail={usingRow ? <LogUseDialog key={`${linked.scope}:${usingRow.id}`} row={usingRow} makerspaceId={makerspace.id} auditHref={staffTabPath("audit", false, makerspace.slug)} canReviewAudit={canReviewAudit} linked={linked} linkedEnabled={capabilityOn(makerspace, "inventory.consumables")} onClose={() => setUsingRow(null)} /> : null} />;
}

function ConsumableListRow({ row, toBuyHref, onUse }: { row: ConsumableRow; toBuyHref: string; onUse?: () => void }) {
  const threshold = row.threshold === null ? "No reorder level" : `reorder at ${row.threshold}`;
  return <ListRow title={row.name} identity={{ kind: "icon", icon: row.status === "low" ? "TriangleAlert" : "Circle", tone: row.status === "low" ? "emphasis" : SOURCE_TONES[row.source] }}
    meta={<><span className="tabular-nums">{row.remaining} {unitLabel(row.unit)}</span> · {threshold}{row.machine_name ? ` · ${row.machine_name}` : ""}</>}
    right={<div className="flex flex-wrap items-center gap-2">
      <StatusPill label={SOURCE_LABELS[row.source]} tone={SOURCE_TONES[row.source]} />
      {row.status === "low" ? <StatusBadge status="low" label={t`Low`} /> : null}
      {row.open_to_buy_id ? <RouteLink className="inline-flex min-h-11 items-center px-1 text-sm font-semibold text-accent-ink underline" href={toBuyHref}>{t`Open To-Buy`}</RouteLink> : null}
      {onUse ? <button type="button" className="desk-button" onClick={onUse}>{t`Log use`}</button> : null}
    </div>} />;
}

function LogUseDialog({ row, makerspaceId, auditHref, canReviewAudit, onClose, linked, linkedEnabled }: { row: ConsumableRow; makerspaceId: number; auditHref: string; canReviewAudit: () => boolean; onClose: () => void; linked: ReturnType<typeof useLinkedUseOwners>; linkedEnabled: boolean }) {
  const client = useQueryClient();
  const [quantity, setQuantity] = useState("1");
  const [note, setNote] = useState("");
  const linkedScope = `${linked.scope}:${row.id}`;
  const [linkedLocked, setLinkedLocked] = useState(() => Boolean(linked.owner(row.id).current(linkedScope)));
  const [ordinaryUnknown, setOrdinaryUnknown] = useState(() => linked.ordinaryUnknown(row.id));
  const amount = Number(quantity);
  const valid = Number.isInteger(amount) && amount >= 1;
  const use = useMutation({
    mutationFn: async (finish: (definite: boolean) => void) => {
      let definite = false;
      try { if (!linked.admitted()) { definite = true; throw new Error(t`Session changed.`); } const result = await logConsumableUse(makerspaceId, row.id, amount, note.trim()); definite = true; return result; }
      catch (error) { if ((error as { status?: number })?.status === 400) definite = true; throw error; }
      finally { finish(definite); if (definite) setOrdinaryUnknown(false); }
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: consumableKeys.all(makerspaceId) });
      void client.invalidateQueries({ queryKey: ["inventory", makerspaceId] });
      onClose();
    },
  });
  return <Modal open onClose={onClose} title={t`Log use of ${row.name}`}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); if (!valid || !linked.admitted() || linked.owner(row.id).current(linkedScope)) return; const finish = linked.beginOrdinary(row.id); if (finish) { setOrdinaryUnknown(true); use.mutate(finish); } }}>
      <p className="text-sm text-muted"><span className="tabular-nums">{row.remaining}</span> {unitLabel(row.unit)}. {t`Used stock is never lent and does not come back.`}</p>
      <Field label={t`How many were used`}><input className="desk-input" type="number" min={1} step={1} required value={quantity} onChange={event => setQuantity(event.target.value)} /></Field>
      <Field label={t`Note (optional)`}><input className="desk-input" maxLength={200} value={note} onChange={event => setNote(event.target.value)} /></Field>
      <ErrorText message={use.error?.message} />
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={!valid || use.isPending || linkedLocked || ordinaryUnknown}>{use.isPending ? t`Saving…` : t`Log use`}</button>
      </div>
    </form>
    {ordinaryUnknown && !use.isPending ? <div className="mt-4 grid gap-2 text-sm" role="status"><p className="text-ink">{t`The result may be unknown. Review the authorized audit history before recording another use.`}</p>
      {canReviewAudit() ? <div className="flex flex-wrap items-center gap-2"><RouteLink className="desk-button" href={auditHref}>{t`Open audit log`}</RouteLink><button type="button" className="desk-button" onClick={() => { if (linked.resolveOrdinary(row.id, canReviewAudit())) setOrdinaryUnknown(false); }}>{t`I reviewed the audit log`}</button></div> : <p>{t`Ask a manager to review the audit log.`}</p>}</div> : null}
    {linkedEnabled && linked.admitted() && !ordinaryUnknown ? <LinkedConsumableUse tenant={makerspaceId} product={row.id} scope={linkedScope} owner={linked.owner(row.id)} admitted={linked.admitted} acquire={() => linked.acquire(row.id)} onLockChange={setLinkedLocked} /> : null}
  </Modal>;
}
