import { t } from "@lingui/core/macro";
import { useContext, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field, Modal, OverflowMenu, PagePager } from "../../components/ui";
import { toast } from "../../components/ui/toastStore";
import { staffRequest } from "../../lib/api";
import type { Paginated } from "../../lib/usePaginatedQuery";
import type { ListState } from "../../lib/useUrlListState";
import { StaffListContext } from "./StaffListContext";
import { SavedViewRow } from "./SavedViewRow";

export type SavedView = { id: number; owner_username: string; name: string; state: ListState; shared: boolean };
/** A ready-made filter with its server-side count (parity E-B5, B25). */
export type ListPreset = { key: string; label: string; filters: Record<string, string>; count: number };

/** The address of the current page with this view's filters applied (under the list's URL prefix). */
export function viewLink(state: ListState, prefix = "") {
  const url = new URL(window.location.href);
  Object.entries(state).forEach(([key, value]) => {
    if (key === "event" || key === "makerspace") return;
    if (value) url.searchParams.set(prefix + key, value); else url.searchParams.delete(prefix + key);
  });
  return url.toString();
}

export async function copyViewLink(state: ListState, prefix = "") {
  try { await navigator.clipboard.writeText(viewLink(state, prefix)); toast(t`Link copied.`); }
  catch { toast(t`Could not copy the link. Copy it from the address bar instead.`, { tone: "error" }); }
}

export function SavedViewsMenu({ makerspaceId, entity, state, onRestore, eventId, presets = [], linkPrefix = "" }: {
  makerspaceId: number; entity: string; state: ListState; onRestore: (state: ListState) => void;
  /** Views saved for ONE event's list (events.event_saved_views); without it, space-wide views. */
  eventId?: number; presets?: ListPreset[]; linkPrefix?: string;
}) {
  const { ownerName, canShare } = useContext(StaffListContext);
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [manage, setManage] = useState(false);
  const [name, setName] = useState("");
  const [shared, setShared] = useState(false);
  const key = ["saved-views", ownerName, makerspaceId, entity, eventId ?? null];
  const base = `/admin/makerspaces/${makerspaceId}/saved-views`;
  const scope = eventId ? `&event=${eventId}` : "";
  const views = useQuery({ queryKey: [...key, page], queryFn: () => staffRequest<Paginated<SavedView>>(`${base}?entity=${entity}${scope}&page=${page}`) });
  const refresh = () => client.invalidateQueries({ queryKey: key });
  const save = useMutation({
    mutationFn: () => staffRequest<SavedView>(base, { method: "POST", body: JSON.stringify({ entity, name: name.trim(), shared,
      state: { ...Object.fromEntries(Object.entries(state).filter(([key]) => key !== "makerspace")), ...(eventId ? { event: String(eventId) } : {}) } }) }),
    onSuccess: () => { setOpen(false); setName(""); setShared(false); void refresh(); },
  });
  const change = useMutation({
    mutationFn: ({ id, body }: { id: number; body?: Partial<Pick<SavedView, "shared" | "name">> }) => staffRequest(`${base}/${id}`, body === undefined
      ? { method: "DELETE" } : { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => { setPage(1); void refresh(); },
  });
  const paging = <PagePager page={page} setPage={setPage} next={views.data?.next} />;
  const mine = (views.data?.results ?? []).filter(view => view.owner_username === ownerName);
  return <div className="flex items-center gap-2">
    <OverflowMenu label={t`Views`} showLabel actions={[
      ...presets.map(preset => ({ label: t`${preset.label} (${preset.count})`, onClick: () => onRestore(preset.filters) })),
      ...(views.data?.results ?? []).map(view => ({ label: view.shared ? t`${view.name} (shared)` : view.name, onClick: () => onRestore(view.state) })),
      ...(views.data?.previous ? [{ label: t`Previous views`, onClick: () => setPage(p => p - 1) }] : []),
      ...(views.data?.next ? [{ label: t`More views`, onClick: () => setPage(p => p + 1) }] : []),
      { label: t`Save current view…`, onClick: () => setOpen(true) },
      { label: t`Copy link to this view`, onClick: () => { void copyViewLink(state, linkPrefix); } },
      { label: t`Manage views…`, onClick: () => setManage(true) },
    ]} />
    {views.error ? <p role="alert" className="text-sm text-danger">{views.error.message}</p> : null}
    <Modal title={t`Manage saved views`} open={manage} onClose={() => { setManage(false); change.reset(); }}>
      <div className="grid gap-3">
        {mine.map(view => <SavedViewRow key={view.id} view={view} canShare={canShare} pending={change.isPending}
          onRename={name => change.mutate({ id: view.id, body: { name } })} onShare={() => change.mutate({ id: view.id, body: { shared: !view.shared } })}
          onDelete={() => change.mutate({ id: view.id })} onCopy={() => { void copyViewLink(view.state, linkPrefix); }} />)}
        {!views.isLoading && !mine.length ? <EmptyState message={t`No personal views on this page. Save the current view to come back to it.`} /> : null}
        {paging}
        {change.error ? <p role="alert" className="text-sm text-danger">{change.error.message}</p> : null}
      </div>
    </Modal>
    {open ? <Modal title={t`Save current view`} open onClose={() => { setOpen(false); save.reset(); }}>
      <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
        <Field label={t`View name`}><input className="desk-input" maxLength={80} required value={name} onChange={(event) => setName(event.target.value)} /></Field>
        {canShare ? <label><input type="checkbox" checked={shared} onChange={(event) => setShared(event.target.checked)} /> {t` Share to this makerspace`}</label> : null}
        {eventId ? <p className="text-sm text-muted">{t`This view is kept with this event's list only.`}</p> : null}
        {save.error ? <p role="alert" className="text-danger">{save.error.message}</p> : null}
        <button className="desk-button-primary" disabled={save.isPending || !name.trim()}>{t`Save view`}</button>
      </form>
    </Modal> : null}
  </div>;
}
