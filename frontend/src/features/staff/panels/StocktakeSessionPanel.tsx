import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { ListLayout, DetailLayout } from "../../../components/layouts";
import { ConfirmDialog, DetailDrawer, ErrorText, Field, ListRow, Modal, RelativeTime, StatusPill } from "../../../components/ui";
import { useSearchParams } from "react-router-dom";
import { inventoryQueryState } from "./inventoryPresentation";
import { StocktakeDiscipline } from "./StocktakeDiscipline";
import { CountSection } from "./StocktakeCountSection";
import { useUrlListState } from "../../../lib/useUrlListState";
import { usePaginatedQuery } from "../../../lib/usePaginatedQuery";
import { type Makerspace, useStaffGet } from "./shared";
import { invalidateInventoryViews } from "../queryInvalidation";

type ContainerOption = { id: number; label: string; location?: string };
type StocktakeRow = { variance_threshold?: number | null; approval_required?: boolean; id: number; status: string; notes: string; container: number | null; started_at?: string; blind?: boolean; lines?: { variance_quantity: number | null }[] };
export function StocktakePanel({ makerspace, isSuperadmin = false, canConfigure = false }: { makerspace: Makerspace; isSuperadmin?: boolean; canConfigure?: boolean }) {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const openId = Number(params.get("session")) || null;
  const [createOpen, setCreateOpen] = useState(false);
  const [policyOpen, setPolicyOpen] = useState(false);
  const [applyTarget, setApplyTarget] = useState<number | null>(null);
  const [blind, setBlind] = useState("");
  const discipline = makerspace.enabled_features?.includes("stocktake.discipline");
  const [createNotes, setCreateNotes] = useState("Cycle count");
  const [createContainerId, setCreateContainerId] = useState("");
  const list = useUrlListState({ status: "", page: "1" });
  const stocktakes = usePaginatedQuery<StocktakeRow>({
    key: ["stocktakes", makerspace.id, list.values.status],
    page: list.page, onPageChange: list.setPage,
    path: `/admin/makerspace/${makerspace.id}/stocktakes?status=${encodeURIComponent(list.values.status)}`,
    resetKey: String(makerspace.id),
  });
  const containers = useStaffGet<{ results: ContainerOption[] }>(["stocktake-containers", makerspace.id], `/admin/makerspace/${makerspace.id}/containers?page_size=1000`);
  const session = useStaffGet<StocktakeRow>(["stocktake-detail", openId], openId ? `/admin/stocktakes/${openId}` : "", Boolean(openId));
  const schedules = usePaginatedQuery<{ id: number; name: string; next_due: string; is_active: boolean }>({ key: ["stocktake-schedules", makerspace.id], path: `/admin/makerspace/${makerspace.id}/stocktake-schedules`, resetKey: String(makerspace.id), enabled: Boolean(discipline && canConfigure) });
  const dueSchedule = schedules.results.find(row => row.is_active && new Date(row.next_due).getTime() <= Date.now());
  const create = useMutation({
    mutationFn: () =>
      staffRequest<StocktakeRow>(`/admin/makerspace/${makerspace.id}/stocktakes`, {
        method: "POST",
        body: JSON.stringify({
          notes: createNotes,
          ...(discipline && blind !== "" ? { blind: blind === "true" } : {}),
          container_id: createContainerId ? Number(createContainerId) : null,
        }),
      }),
    onSuccess: created => { setCreateOpen(false); setParams(current => { current.set("session", String(created.id)); return current; }); queryClient.invalidateQueries({ queryKey: ["stocktakes", makerspace.id] }); },
  });
  const action = useMutation({
    mutationFn: (path: string) => staffRequest(path, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (_data, path) => {
      setApplyTarget(null);
      if (openId) queryClient.invalidateQueries({ queryKey: ["stocktake-detail", openId] });
      queryClient.invalidateQueries({ queryKey: ["stocktakes", makerspace.id] });
      if (path.endsWith("/apply-adjustments")) {
        invalidateInventoryViews(queryClient, makerspace.id);
        queryClient.invalidateQueries({ queryKey: ["needs-fix-shelf", makerspace.id] });
      }
    },
  });
  const createError = create.error instanceof Error ? create.error.message : undefined;
  const actionError = action.error instanceof Error ? action.error.message : undefined;

  const href = (status: string) => { const next = new URLSearchParams(params); next.set("status", status); next.delete("page"); return `?${next}`; };
  const close = () => setParams(current => { current.delete("session"); return current; });
  const selected = session.data ?? stocktakes.results.find(row => row.id === openId);
  const nextAction = (row: StocktakeRow) => {
    if (row.status === "counting") return { label: "Complete count", pending: action.isPending, onClick: () => action.mutate(`/admin/stocktakes/${row.id}/complete`) };
    if ((isSuperadmin || (canConfigure && row.variance_threshold != null)) && row.status === "completed") return { label: "Approve", pending: action.isPending, onClick: () => action.mutate(`/admin/stocktakes/${row.id}/approve`) };
    if ((isSuperadmin || row.approval_required === false || (canConfigure && row.variance_threshold != null)) && row.status === "approved") return { label: "Apply adjustments", confirms: true, pending: action.isPending, onClick: () => setApplyTarget(row.id) };
    return undefined;
  };
  const add = { label: "Start count", onClick: () => setCreateOpen(true) };
  const detail = <><Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Start count" footer={<button className="desk-button-primary" disabled={create.isPending} onClick={() => create.mutate()}>{create.isPending ? "Starting…" : "Start stocktake"}</button>}>
    <div className="grid gap-4"><Field label="Session notes"><input className="desk-input" value={createNotes} onChange={event => setCreateNotes(event.target.value)} /></Field>
      <Field label="Container"><select className="desk-input" value={createContainerId} onChange={event => setCreateContainerId(event.target.value)}><option value="">All containers</option>{containers.data?.results.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></Field>
      {discipline ? <Field label="Count visibility"><select className="desk-input" value={blind} onChange={event => setBlind(event.target.value)}><option value="">Use makerspace policy</option><option value="true">Blind (hide expected quantities)</option><option value="false">Show expected quantities</option></select></Field> : null}
      <ErrorText message={createError || containers.error?.message} /></div>
    </Modal>
    {discipline && canConfigure ? <DetailDrawer open={policyOpen} onClose={() => setPolicyOpen(false)} title="Count policy and schedule"><StocktakeDiscipline makerspaceId={makerspace.id} /></DetailDrawer> : null}
    <ConfirmDialog open={applyTarget !== null} title={selected?.lines ? `Apply ${selected.lines.filter(line => line.variance_quantity != null && line.variance_quantity !== 0).length} adjustments?` : "Apply adjustments?"} message="Inventory numbers will change to match this approved count." confirmLabel="Apply adjustments" pending={action.isPending} onCancel={() => setApplyTarget(null)} onConfirm={() => { if (applyTarget) action.mutate(`/admin/stocktakes/${applyTarget}/apply-adjustments`); }} />
    <ErrorText message={actionError} />
  </>;
  if (openId) return <><DetailLayout title={selected?.notes || "Stocktake session"} back={{ label: "All counts", onClick: close }}
    identity={{ kind: "icon", icon: "Circle", tone: "accent" }} status={selected ? <StatusPill label={selected.status.replace(/_/g, " ")} /> : undefined}
    meta={selected ? [`#${selected.id}`, selected.started_at ? <>Started <RelativeTime date={selected.started_at} /></> : "", selected.blind ? "Blind count" : "Expected shown"] : undefined}
    state={inventoryQueryState(session, "this count")} actions={{ primary: selected ? nextAction(selected) : undefined }}
    main={<CountSection makerspace={makerspace} stocktakeId={openId} readOnly={selected ? !canCount(selected.status) : undefined} />} />{detail}</>;
  return <ListLayout header={{ title: "Stocktake", subtitle: "Count what's on the shelves and fix the numbers.", primary: add,
    overflow: discipline && canConfigure ? [{ label: "Count policy and schedule", onClick: () => setPolicyOpen(true) }] : [] }}
    callout={dueSchedule ? { size: "banner", tone: "warn", lead: `${dueSchedule.name} is due.`, body: "Start a count to check the shelves.", action: { label: "Start it", onClick: () => { setCreateNotes(dueSchedule.name); setCreateOpen(true); } } } : undefined}
    state={inventoryQueryState(stocktakes, "stocktake sessions")} isEmpty={!stocktakes.results.length} filtered={Boolean(list.values.status)}
    empty={{ message: "No counts yet. Start a count to check the shelves against the system.", action: add }}
    filteredEmpty={{ message: list.values.status === "completed" ? "Nothing waiting for approval." : "No counts in this stage.", action: { label: "Clear filters", href: href("") } }}
    tabs={["", "draft", "counting", "completed", "approved", "applied", "cancelled"].map(key => ({ key, label: ({ "": "All", draft: "Draft", counting: "Counting", completed: "Needs approval", approved: "Ready to apply", applied: "Applied", cancelled: "Cancelled" } as Record<string, string>)[key], href: href(key) }))} activeTab={list.values.status}
    body={{ kind: "rows", rows: stocktakes.results.map(row => <ListRow key={row.id} title={row.notes || `Count of ${containers.data?.results.find(container => container.id === row.container)?.label ?? "all containers"}`}
      identity={{ kind: "icon", icon: "Circle", tone: "accent" }} meta={<>#{row.id} · {row.container ? containers.data?.results.find(container => container.id === row.container)?.label : "All containers"}{row.started_at ? <> · Started <RelativeTime date={row.started_at} /></> : null}{row.lines ? ` · ${row.lines.length} lines counted` : ""}</>}
      onClick={() => setParams(current => { current.set("session", String(row.id)); return current; })}
      right={<div className="flex items-center gap-3"><StatusPill label={row.status.replace(/_/g, " ")} />
        {(() => { const next = canCount(row.status) ? undefined : nextAction(row);
          return next ? <button className="desk-button-ghost" disabled={next.pending} onClick={event => { event.stopPropagation(); next.onClick(); }}>{next.label}</button>
            : <button className="desk-button-ghost" onClick={() => setParams(current => { current.set("session", String(row.id)); return current; })}>{canCount(row.status) ? "Continue" : "Open count"}</button>; })()}</div>} />) }}
    pagination={{ page: stocktakes.page, pageSize: stocktakes.pageSize, count: stocktakes.count, onChange: stocktakes.setPage }} detail={detail} />;
}
function canCount(status: string) { return status === "draft" || status === "counting"; }
