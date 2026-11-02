import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ListLayout } from "../../../../../components/layouts";
import { ListRow, StatusPill } from "../../../../../components/ui";
import type { Machine } from "../../../machinesApi";
import { opsQueryState } from "../../../opsPresentation";
import { WorkOrderCreateDialog } from "./WorkOrderCreateDialog";
import { WorkOrderDetail } from "./WorkOrderDetail";
import { PRIORITY_LABELS, STATUS_LABELS, priorityTone, statusTone, useWorkOrders, type WorkOrder } from "./workOrdersApi";

const FILTERS = [
  { key: "open", label: "Open", query: "status=open,in_progress,on_hold" },
  { key: "closed", label: "Closed", query: "status=done,cancelled" },
  { key: "all", label: "All", query: "" },
];

/** The work-order list (`?view=work-orders`) and, with `&work_order=<id>`, one order's detail. */
export function WorkOrdersScreen({ makerspaceId, machines, onBack }: { makerspaceId: number; machines: Machine[]; onBack: () => void }) {
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const filter = FILTERS.find(row => row.key === params.get("wo_status")) ?? FILTERS[0];
  const selectedId = Number(params.get("work_order")) || null;
  // The detail reads from the unfiltered list: a just-closed order must stay visible on its own page.
  const orders = useWorkOrders(makerspaceId, selectedId ? "" : filter.query);
  const setParam = (key: string, value: string | null) => setParams(current => {
    const next = new URLSearchParams(current);
    if (value === null) next.delete(key); else next.set(key, value);
    return next;
  });
  const rows = orders.data ?? [];
  if (selectedId) return <WorkOrderDetail order={rows.find(row => row.id === selectedId)} state={opsQueryState(orders, "work order")}
    onBack={() => setParam("work_order", null)} />;
  return <>
    <ListLayout header={{ title: "Work orders", subtitle: "Repairs and jobs on your machines, from report to fix.",
      primary: { label: "New work order", icon: "Plus", onClick: () => setCreating(true) }, secondary: { label: "All machines", onClick: onBack } }}
      tabs={FILTERS.map(row => ({ key: row.key, label: row.label, href: "#" }))} activeTab={filter.key} onTabChange={key => setParam("wo_status", key)}
      state={opsQueryState(orders, "work orders")} isEmpty={!rows.length}
      empty={{ message: filter.key === "open" ? "No open work orders. Report a problem with New work order." : "No work orders here yet." }}
      body={{ kind: "rows", rows: rows.map(order => <WorkOrderRow key={order.id} order={order} onOpen={() => setParam("work_order", String(order.id))} />) }} />
    {creating ? <WorkOrderCreateDialog makerspaceId={makerspaceId} machines={machines} onClose={() => setCreating(false)}
      onCreated={order => setParam("work_order", String(order.id))} /> : null}
  </>;
}

export function WorkOrderRow({ order, onOpen }: { order: WorkOrder; onOpen: () => void }) {
  return <ListRow title={order.title} onClick={onOpen} identity={{ kind: "icon", icon: "Wrench", tone: "accent" }}
    meta={[order.subject_label, order.due_on ? `Due ${new Date(`${order.due_on}T00:00:00`).toLocaleDateString()}` : "", order.takes_machine_down ? "Takes the machine down" : ""].filter(Boolean).join(" · ")}
    right={<span className="flex flex-wrap gap-1.5"><StatusPill tone={statusTone(order.status)} label={STATUS_LABELS[order.status]} />
      {order.priority !== "normal" ? <StatusPill tone={priorityTone(order.priority)} label={PRIORITY_LABELS[order.priority]} /> : null}</span>} />;
}
