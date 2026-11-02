import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { EmptyState, ErrorBlock } from "../../../../../components/ui";
import { WorkOrderCreateDialog } from "./WorkOrderCreateDialog";
import { WorkOrderRow } from "./WorkOrdersScreen";
import { useWorkOrders } from "./workOrdersApi";

/** The machine drawer's open work orders; each opens on the work-order screen, which replaces the drawer. */
export function MachineWorkOrders({ makerspaceId, machineId, canCreate }: { makerspaceId: number; machineId: number; canCreate: boolean }) {
  const orders = useWorkOrders(makerspaceId, `status=open,in_progress,on_hold&machine=${machineId}`);
  const [, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const openScreen = (id?: number) => setParams(new URLSearchParams({ view: "work-orders", ...(id ? { work_order: String(id) } : {}) }));
  const rows = orders.data ?? [];
  return <section className="grid gap-3" aria-labelledby={`work-orders-${machineId}`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 id={`work-orders-${machineId}`} className="title-section">Work orders</h3>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button-ghost" onClick={() => openScreen()}>All work orders</button>
        {canCreate ? <button type="button" className="desk-button-primary" onClick={() => setCreating(true)}>New work order</button> : null}
      </div>
    </div>
    {orders.error ? <ErrorBlock error={orders.error} resource="work orders" onRetry={() => { void orders.refetch(); }} /> : null}
    {orders.isLoading ? <p role="status" className="text-sm text-muted">Loading work orders…</p> : null}
    {orders.isSuccess && !rows.length ? <EmptyState message="No open work orders for this machine." /> : null}
    {rows.length ? <div className="grid gap-2">{rows.map(order => <WorkOrderRow key={order.id} order={order} onOpen={() => openScreen(order.id)} />)}</div> : null}
    {creating ? <WorkOrderCreateDialog makerspaceId={makerspaceId} machineId={machineId} onClose={() => setCreating(false)} /> : null}
  </section>;
}
