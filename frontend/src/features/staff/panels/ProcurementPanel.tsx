import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Field, Modal, ErrorText } from "../../../components/ui";
import { downloadStaffFile, staffRequest } from "../../../lib/api";
import {
  groupProcurementRows,
  ProcurementRow,
  itemTotal,
  labelStatus,
  statusOptions,
  type Kind,
  type ToBuyItem,
  type ToBuyStatus,
} from "./ProcurementPanelRows";
import {
  procurementMachineTypeOptions,
  procurementMachineTypeRequired,
  type ProcurementMachineTypeOptions,
} from "./ProcurementPanelTypes";
import { ProcurementMoveModal } from "./ProcurementMoveModal";
import { RefillConsumableDialog } from "./RefillConsumableDialog";
import { ReorderSuggestions } from "./ReorderSuggestions";
import { ListLayout } from "../../../components/layouts";
import { useSearchParams } from "react-router-dom";
import { inventoryQueryState } from "./inventoryPresentation";
import { type Makerspace, useStaffGet } from "./shared";
import { capabilityOn } from "../../../lib/features";
import { invalidateFinance } from "../../finance/financeApi";
import { MarkBoughtDialog } from "./MarkBoughtDialog";
import { VendorsPanel } from "./VendorsPanel";
import { AreaOverviewPage } from "../areaOverview/AreaOverviewPage";

type StatusFilter = "all" | ToBuyStatus;
type UpdateVariables = { id: number; payload: { status: ToBuyStatus; vendor_name: string; actual_unit_cost: number | null } };

type Form = {
  name: string;
  quantity: string;
  link: string;
  estimated_unit_cost: string;
  vendor_name: string;
  actual_unit_cost: string;
  kind: Kind;
  machine_type: string;
};

const emptyForm: Form = {
  name: "",
  quantity: "1",
  link: "",
  estimated_unit_cost: "",
  vendor_name: "",
  actual_unit_cost: "",
  kind: "hardware",
  machine_type: "",
};

type ProcurementPanelProps = {
  makerspace: Makerspace;
  canChooseKind?: boolean;
  inventoryTabAvailable?: boolean;
};

export function ProcurementPanel({
  makerspace,
  canChooseKind = false,
  inventoryTabAvailable = false,
}: ProcurementPanelProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Form>(emptyForm);
  const [params, setParams] = useSearchParams();
  const statusFilter = (params.get("status") ?? "requested") as StatusFilter;
  const [addOpen, setAddOpen] = useState(false);
  const [moveTarget, setMoveTarget] = useState<ToBuyItem | null>(null);
  const [boughtTarget, setBoughtTarget] = useState<ToBuyItem | null>(null);
  const vendorsEnabled = capabilityOn(makerspace, "inventory.vendors");
  const base = `/procurement/makerspace/${makerspace.id}/to-buy`;
  const statusParam = statusFilter === "all" ? "" : `&status=${statusFilter}`;
  const queryKey = ["procurement", makerspace.id, statusFilter];
  const items = useStaffGet<ToBuyItem[]>(queryKey, `${base}?limit=200${statusParam}`);
  const machineTypes = useStaffGet<ProcurementMachineTypeOptions>(
    ["procurement-machine-types", makerspace.id, form.kind],
    `${base}/machine-types?kind=${form.kind}`,
  );
  const typeOptions = procurementMachineTypeOptions(machineTypes.data);
  // Server-derived, and it already accounts for the stream, so it needs no local
  // `createsPrintingByDefault` qualifier.
  const requiresMachineType = procurementMachineTypeRequired(machineTypes.data);
  const invalidate = () => void Promise.all([
    queryClient.invalidateQueries({ queryKey: ["procurement", makerspace.id] }),
    queryClient.invalidateQueries({ queryKey: ["operations-report"] }),
  ]);

  const create = useMutation({
    mutationFn: () => {
      const path = canChooseKind ? `${base}?kind=${form.kind}` : base;
      return staffRequest(path, {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          quantity: Number(form.quantity) || 1,
          link: form.link,
          estimated_unit_cost: form.estimated_unit_cost ? Number(form.estimated_unit_cost) : null,
          vendor_name: form.vendor_name,
          actual_unit_cost: form.actual_unit_cost ? Number(form.actual_unit_cost) : null,
          machine_type: form.machine_type ? Number(form.machine_type) : null,
        }),
      });
    },
    onSuccess: () => {
      setForm(emptyForm);
      setAddOpen(false);
      invalidate();
    },
  });

  const update = useMutation({
    mutationFn: (vars: UpdateVariables) =>
      staffRequest(`/procurement/to-buy/${vars.id}`, {
        method: "PATCH",
        body: JSON.stringify(vars.payload),
      }),
    onSuccess: invalidate,
  });

  const remove = useMutation({
    mutationFn: (id: number) => staffRequest(`/procurement/to-buy/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });

  const exportToBuy = useMutation({
    mutationFn: (format: "csv" | "xlsx") => {
      const params = new URLSearchParams({ format });
      if (statusFilter !== "all") params.set("status", statusFilter);
      return downloadStaffFile(`${base}/export?${params.toString()}`, `to-buy-${makerspace.slug}.${format}`);
    },
  });

  const rows = items.data ?? [];
  const visibleEstimatedTotal = rows.reduce((sum, item) => sum + itemTotal(item, "estimated"), 0);
  const openBudget = rows.filter((item) => !["received", "cancelled"].includes(item.status)).reduce((sum, item) => sum + itemTotal(item, "estimated"), 0);
  const receivedTotal = rows.filter((item) => item.status === "received").reduce((sum, item) => sum + itemTotal(item, "actual"), 0);

  const add = { label: t`Add item`, onClick: () => setAddOpen(true) };
  const tabHref = (status: string) => { const next = new URLSearchParams(params); next.set("status", status); return `?${next}`; };
  const showView = (view: string) => setParams(current => { const next = new URLSearchParams(current); if (view) next.set("view", view); else next.delete("view"); return next; });
  if (vendorsEnabled && params.get("view") === "vendors") return <VendorsPanel makerspaceId={makerspace.id} onBack={() => showView("")} />;
  // Decision 241: the same list grouped by area, machine type then machine, and item category.
  if (params.get("view") === "groups") return <AreaOverviewPage title={t`To buy, grouped`} makerspaceId={makerspace.id} section="tobuy" onBack={() => showView("")} />;
  return <ListLayout header={{ title: t`To buy`, subtitle: t`What the space needs, from request to shelf.`, primary: add,
    secondary: vendorsEnabled ? { label: t`Vendors`, onClick: () => showView("vendors") } : undefined,
    overflow: [{ label: t`Group by area and machine`, onClick: () => showView("groups") }, { label: t`Export CSV`, pending: exportToBuy.isPending, onClick: () => exportToBuy.mutate("csv") }, { label: t`Export Excel`, pending: exportToBuy.isPending, onClick: () => exportToBuy.mutate("xlsx") }] }}
    callout={rows.some(item => item.status === "received" && !item.moved_to_inventory_at) ? { size: "banner", tone: "warn", lead: "Received items aren't in inventory yet.", body: t`Move a purchase onto the shelves when it's ready.`, action: { label: t`Move them`, onClick: () => setMoveTarget(rows.find(item => item.status === "received" && !item.moved_to_inventory_at)!) } } : undefined}
    state={inventoryQueryState(items, "the list")} isEmpty={!rows.length} filtered={statusFilter !== "all"}
    empty={{ message: t`Nothing on the list yet. Add the first thing your space needs.`, action: add }}
    filteredEmpty={{ message: t`Nothing in this stage yet. Add an item or view all stages.`, action: { label: t`View all`, href: tabHref("all") } }}
    stats={[{ label: t`Estimated total (visible)`, value: formatAmount(visibleEstimatedTotal) }, { label: t`Open budget`, value: formatAmount(openBudget) }, { label: t`Spent (received)`, value: formatAmount(receivedTotal) }]}
    tabs={[...statusOptions, "all"].map(status => ({ key: status, label: status === "all" ? t`All` : labelStatus(status as ToBuyStatus), href: tabHref(status) }))} activeTab={statusFilter}
    body={{ kind: "rows", rows: groupProcurementRows(rows).map(group => <section key={group.key} className="grid gap-3"><h2 className="title-section">{group.label}</h2>
      {group.rows.map(item => <ProcurementRow key={item.id} item={item} makerspaceSlug={makerspace.slug} updatePending={update.isPending && update.variables?.id === item.id} deletePending={remove.isPending && remove.variables === item.id}
        onSave={draft => update.mutate({ id: item.id, payload: { status: draft.status, vendor_name: draft.vendor_name, actual_unit_cost: draft.actual_unit_cost ? Number(draft.actual_unit_cost) : null } })}
        onDelete={() => remove.mutate(item.id)} onMove={() => setMoveTarget(item)} onReceiptsChanged={invalidate} onMarkBought={() => setBoughtTarget(item)}
        updateError={update.variables?.id === item.id ? update.error?.message : undefined} deleteError={remove.variables === item.id ? remove.error?.message : undefined} />)}</section>) }}
    detail={<>{inventoryTabAvailable ? <ReorderSuggestions makerspaceId={makerspace.id} canProcure /> : null}<Modal open={addOpen} onClose={() => setAddOpen(false)} title={t`Add item`}>
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); if (form.name.trim() && (!requiresMachineType || form.machine_type)) create.mutate(); }}>
        <Field label={t`Item name`} className="sm:col-span-2"><input className="desk-input sm:col-span-2" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label={t`Quantity`}><input className="desk-input" type="number" min={1} value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
        <Field label={t`Link (optional)`}><input className="desk-input" value={form.link} onChange={(e) => setForm({ ...form, link: e.target.value })} /></Field>
        <Field label={t`Estimated unit cost`}><input className="desk-input" type="number" min={0} step="any" value={form.estimated_unit_cost} onChange={(e) => setForm({ ...form, estimated_unit_cost: e.target.value })} /></Field>
        <Field label={t`Vendor`}><input className="desk-input" value={form.vendor_name} onChange={(e) => setForm({ ...form, vendor_name: e.target.value })} /></Field>
        <Field label={t`Actual unit cost`}><input className="desk-input" type="number" min={0} step="any" value={form.actual_unit_cost} onChange={(e) => setForm({ ...form, actual_unit_cost: e.target.value })} /></Field>
        <label className="eyebrow grid gap-1">
          {t`Machine type`}<select
            className="desk-input"
            value={form.machine_type}
            onChange={(event) => setForm({ ...form, machine_type: event.target.value })}
            required={requiresMachineType}
          >
            <option value="">{requiresMachineType ? t`Select a type` : t`Unassigned`}</option>
            {typeOptions.map((machineType) => (
              <option key={machineType.id} value={machineType.id}>{machineType.name}</option>
            ))}
          </select>
          {requiresMachineType && !machineTypes.isLoading && !typeOptions.length ? (
            <span className="normal-case tracking-normal text-danger">{t`No machine types are linked to your role.`}</span>
          ) : null}
        </label>
        {canChooseKind ? <KindSelect value={form.kind} onChange={(kind) => setForm({ ...form, kind })} /> : <AddButton disabled={create.isPending || !form.name.trim() || (requiresMachineType && !form.machine_type)} label={create.isPending ? t`Adding…` : t`Add`} />}
        {canChooseKind ? <AddButton disabled={create.isPending || !form.name.trim() || (requiresMachineType && !form.machine_type)} label={create.isPending ? t`Adding…` : t`Add item`} className="sm:col-span-2" /> : null}
      </form>
        <ErrorText message={create.error?.message || machineTypes.error?.message} />
      </Modal><ErrorText message={exportToBuy.error?.message} />
      <ProcurementMoveModal item={moveTarget?.source_consumable ? null : moveTarget} makerspace={makerspace} onClose={() => setMoveTarget(null)} onMoved={invalidate} />
      {moveTarget?.source_consumable ? <RefillConsumableDialog key={moveTarget.id} item={moveTarget} onClose={() => setMoveTarget(null)}
        onDone={() => { invalidate(); void queryClient.invalidateQueries({ queryKey: ["consumables", makerspace.id] }); }} /> : null}
      {boughtTarget ? <MarkBoughtDialog key={boughtTarget.id} item={boughtTarget} makerspaceId={makerspace.id} vendorsEnabled={vendorsEnabled}
        onClose={() => setBoughtTarget(null)} onDone={() => { setBoughtTarget(null); invalidate(); invalidateFinance(queryClient, makerspace.id);
          void queryClient.invalidateQueries({ queryKey: ["consumables", makerspace.id] }); }} /> : null}
    </>} />;
}
function KindSelect({ value, onChange }: { value: Kind; onChange: (kind: Kind) => void }) {
 return <Field label={t`Kind`}><select className="desk-input" value={value} onChange={e => onChange(e.target.value as Kind)}><option value="hardware">{t`Hardware`}</option><option value="printing">{t`Printing`}</option></select></Field>;
}
function AddButton({ disabled, label, className = "" }: { disabled: boolean; label: string; className?: string }) {
 return <button className={`desk-button-primary ${className}`} type="submit" disabled={disabled}>{label}</button>;
}
function formatAmount(value: number) { return value.toLocaleString(formatLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
