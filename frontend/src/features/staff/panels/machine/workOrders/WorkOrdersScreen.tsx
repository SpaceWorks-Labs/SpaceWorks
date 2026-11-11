import { formatLocale } from "../../../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ListLayout } from "../../../../../components/layouts";
import { ListRow, StatusPill } from "../../../../../components/ui";
import type { Machine } from "../../../machinesApi";
import { opsQueryState } from "../../../opsPresentation";
import { SavedViewsMenu } from "../../../SavedViewsMenu";
import { WorkOrderCreateDialog } from "./WorkOrderCreateDialog";
import { WorkOrderDetail } from "./WorkOrderDetail";
import { PRIORITY_LABELS, STATUS_LABELS, priorityTone, statusTone, useWorkOrders, type WorkOrder } from "./workOrdersApi";

const FILTERS = [
  { key: "open", label: t`Open`, query: "status=open,in_progress,on_hold" },
  { key: "closed", label: t`Closed`, query: "status=done,cancelled" },
  { key: "all", label: t`All`, query: "" },
];

/** The work-order list (`?view=work-orders`) and, with `&work_order=<id>`, one order's detail. */
export function WorkOrdersScreen({ makerspaceId, machines, onBack }: { makerspaceId: number; machines: Machine[]; onBack: () => void }) {
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const filter = FILTERS.find(row => row.key === params.get("wo_status")) ?? FILTERS[0];
  const selectedId = Number(params.get("work_order")) || null;
  // A16: the machine filter (`wo_machine`) narrows on the server, like the status tabs.
  const machine = /^\d+$/.test(params.get("wo_machine") ?? "") ? params.get("wo_machine")! : "";
  const listQuery = [filter.query, machine ? `machine=${machine}` : ""].filter(Boolean).join("&");
  // The detail reads from the unfiltered list: a just-closed order must stay visible on its own page.
  const orders = useWorkOrders(makerspaceId, selectedId ? "" : listQuery);
  const setParam = (key: string, value: string | null) => setParams(current => {
    const next = new URLSearchParams(current);
    if (value === null) next.delete(key); else next.set(key, value);
    return next;
  });
  const rows = orders.data ?? [];
  if (selectedId) return <WorkOrderDetail order={rows.find(row => row.id === selectedId)} state={opsQueryState(orders, "work order")}
    onBack={() => setParam("work_order", null)} />;
  return <>
    <ListLayout header={{ title: t`Work orders`, subtitle: t`Repairs and jobs on your machines, from report to fix.`,
      primary: { label: t`New work order`, icon: "Plus", onClick: () => setCreating(true) }, secondary: { label: t`All machines`, onClick: onBack } }}
      tabs={FILTERS.map(row => ({ key: row.key, label: row.label, href: "#" }))} activeTab={filter.key} onTabChange={key => setParam("wo_status", key)}
      filters={{ activeCount: machine ? 1 : 0, onClear: () => setParam("wo_machine", null),
        views: <SavedViewsMenu makerspaceId={makerspaceId} entity="work_orders" state={{ status: filter.key, machine }}
          onRestore={state => setParams(current => { const next = new URLSearchParams(current);
            next.set("wo_status", state.status || "open"); if (state.machine) next.set("wo_machine", state.machine); else next.delete("wo_machine"); return next; })} />,
        controls: <label className="eyebrow grid gap-1">{t`Machine`}
          <select className="desk-input" value={machine} onChange={event => setParam("wo_machine", event.target.value || null)}>
            <option value="">{t`All machines`}</option>{machines.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select></label> }} filtered={Boolean(machine)}
      filteredEmpty={{ message: t`No work orders on this machine here.`, action: { label: t`All machines`, onClick: () => setParam("wo_machine", null) } }}
      state={opsQueryState(orders, "work orders")} isEmpty={!rows.length}
      empty={{ message: filter.key === "open" ? t`No open work orders. Report a problem with New work order.` : t`No work orders here yet.` }}
      body={{ kind: "rows", rows: rows.map(order => <WorkOrderRow key={order.id} order={order} onOpen={() => setParam("work_order", String(order.id))} />) }} />
    {creating ? <WorkOrderCreateDialog makerspaceId={makerspaceId} machines={machines} onClose={() => setCreating(false)}
      onCreated={order => setParam("work_order", String(order.id))} /> : null}
  </>;
}

export function WorkOrderRow({ order, onOpen }: { order: WorkOrder; onOpen: () => void }) {
  return <ListRow title={order.title} onClick={onOpen} identity={{ kind: "icon", icon: "Wrench", tone: "accent" }}
    meta={[order.subject_label, order.due_on ? `Due ${new Date(`${order.due_on}T00:00:00`).toLocaleDateString(formatLocale())}` : "", order.takes_machine_down ? "Takes the machine down" : ""].filter(Boolean).join(" · ")}
    right={<span className="flex flex-wrap gap-1.5"><StatusPill tone={statusTone(order.status)} label={STATUS_LABELS[order.status]} />
      {order.priority !== "normal" ? <StatusPill tone={priorityTone(order.priority)} label={PRIORITY_LABELS[order.priority]} /> : null}</span>} />;
}
