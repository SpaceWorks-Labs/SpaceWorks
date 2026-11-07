import { t } from "@lingui/core/macro";
import { useContext, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field, Modal, OverflowMenu } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import type { Paginated } from "../../lib/usePaginatedQuery";
import type { ListState } from "../../lib/useUrlListState";
import { StaffListContext } from "./StaffListContext";

type SavedView = { id: number; owner_username: string; name: string; state: ListState; shared: boolean };

export function SavedViewsMenu({ makerspaceId, entity, state, onRestore }: {
  makerspaceId: number; entity: string; state: ListState; onRestore: (state: ListState) => void;
}) {
  const { ownerName, canShare } = useContext(StaffListContext);
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [manage, setManage] = useState(false);
  const [name, setName] = useState("");
  const [shared, setShared] = useState(false);
  const key = ["saved-views", ownerName, makerspaceId, entity];
  const base = `/admin/makerspaces/${makerspaceId}/saved-views`;
  const views = useQuery({ queryKey: [...key, page], queryFn: () => staffRequest<Paginated<SavedView>>(`${base}?entity=${entity}&page=${page}`) });
  const refresh = () => client.invalidateQueries({ queryKey: key });
  const save = useMutation({
    mutationFn: () => staffRequest<SavedView>(base, { method: "POST", body: JSON.stringify({ entity, name: name.trim(), state: Object.fromEntries(Object.entries(state).filter(([key]) => key !== "makerspace")), shared }) }),
    onSuccess: () => { setOpen(false); setName(""); setShared(false); void refresh(); },
  });
  const change = useMutation({
    mutationFn: ({ id, publish }: { id: number; publish?: boolean }) => staffRequest(`${base}/${id}`, publish === undefined
      ? { method: "DELETE" } : { method: "PATCH", body: JSON.stringify({ shared: publish }) }),
    onSuccess: () => { setPage(1); void refresh(); },
  });
  const paging = <div className="flex flex-wrap gap-2">
    {views.data?.previous ? <button type="button" className="desk-button" onClick={() => setPage(p => p - 1)}>{t`Previous views`}</button> : null}
    {views.data?.next ? <button type="button" className="desk-button" onClick={() => setPage(p => p + 1)}>{t`More views`}</button> : null}
  </div>;
  return <div className="flex items-center gap-2">
    <OverflowMenu label={t`Views`} showLabel actions={[
      ...(views.data?.results ?? []).map(view => ({ label: `${view.name}${view.shared ? " (shared)" : ""}`, onClick: () => onRestore(view.state) })),
      ...(views.data?.previous ? [{ label: t`Previous views`, onClick: () => setPage(p => p - 1) }] : []),
      ...(views.data?.next ? [{ label: t`More views`, onClick: () => setPage(p => p + 1) }] : []),
      { label: t`Save current view…`, onClick: () => setOpen(true) },
      { label: t`Manage views…`, onClick: () => setManage(true) },
    ]} />
    {views.error ? <p role="alert" className="text-sm text-danger">{views.error.message}</p> : null}
    <Modal title={t`Manage saved views`} open={manage} onClose={() => { setManage(false); change.reset(); }}>
      <div className="grid gap-3">
        {(views.data?.results ?? []).filter(view => view.owner_username === ownerName).map(view => <div key={view.id} className="grid gap-2 border-b border-line pb-3">
          <span className="font-semibold">{view.name}</span>
          <div className="flex flex-wrap gap-2">{canShare ? <button type="button" className="desk-button" disabled={change.isPending} onClick={() => change.mutate({ id: view.id, publish: !view.shared })}>{view.shared ? t`Make private` : t`Share to makerspace`}</button> : null}
            <button type="button" className="desk-button-ghost text-danger" disabled={change.isPending} onClick={() => change.mutate({ id: view.id })}>{t`Delete ${view.name}`}</button></div>
        </div>)}
        {!views.isLoading && !views.data?.results?.some(view => view.owner_username === ownerName) ? <EmptyState message={t`No personal views on this page. Save the current view to come back to it.`} /> : null}
        {paging}
        {change.error ? <p role="alert" className="text-sm text-danger">{change.error.message}</p> : null}
      </div>
    </Modal>
    {open ? <Modal title={t`Save current view`} open onClose={() => { setOpen(false); save.reset(); }}>
      <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
        <Field label={t`View name`}><input className="desk-input" maxLength={80} required value={name} onChange={(event) => setName(event.target.value)} /></Field>
        {canShare ? <label><input type="checkbox" checked={shared} onChange={(event) => setShared(event.target.checked)} /> {t` Share to this makerspace`}</label> : null}
        {save.error ? <p role="alert" className="text-danger">{save.error.message}</p> : null}
        <button className="desk-button-primary" disabled={save.isPending || !name.trim()}>{t`Save view`}</button>
      </form>
    </Modal> : null}
  </div>;
}
