import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog, PagePager } from "../../../components/ui";
import { deleteReportView, getReportView, listReportViews, saveReportView, type ReportViewState } from "./reportViewsApi";
import { reportFieldLabel } from "./reportFieldLabels";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";

export function ServerReportViews({ makerspaceId, state, fields, onColumns, onApply }: {
  makerspaceId: number; state: ReportViewState; fields: string[];
  onColumns: (columns: string[]) => void; onApply: (state: ReportViewState) => void;
}) {
  const client = useQueryClient();
  const [deleting, setDeleting] = useState<{ id: number; name: string } | null>(null);
  const [name, setName] = useState("");
  const [shared, setShared] = useState(false);
  const [page, setPage] = useState(1);
  const key = ["saved-report-views", makerspaceId];
  const views = useQuery({ queryKey: [...key, page], queryFn: () => listReportViews(makerspaceId, page) });
  const refresh = () => client.invalidateQueries({ queryKey: key });
  const save = useMutation({
    mutationFn: () => saveReportView(makerspaceId, name.trim(), state, shared),
    onSuccess: () => { setName(""); refresh(); },
  });
  // Fetch at open time: a cached shared view cannot bypass owner reauthorization.
  const open = useMutation({ mutationFn: (pk: number) => getReportView(makerspaceId, pk), onSuccess: (view) => onApply(view.state) });
  const remove = useMutation({ mutationFn: (pk: number) => deleteReportView(makerspaceId, pk), onSuccess: () => { setDeleting(null); refresh(); } });
  const error = save.error ?? open.error ?? remove.error ?? views.error;
  return <div className="mt-4 space-y-3 border-t border-line pt-3">
    <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
      <label className="eyebrow grid gap-1">{t`View name`}<input className="desk-input" value={name} maxLength={80} onChange={(event) => setName(event.target.value)} required /></label>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={shared} onChange={(event) => setShared(event.target.checked)} />{t`Share with makerspace (managers)`}</label>
      <button className="desk-button-primary" disabled={!name.trim() || save.isPending}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save view`}</button>
    </form>
    <fieldset className="flex flex-wrap gap-2"><legend className="eyebrow">{t`Visible columns (none selected shows all)`}</legend>
      {fields.map((field) => <label className="flex min-h-11 items-center gap-2 text-sm" key={field}><input type="checkbox" checked={state.columns.includes(field)} onChange={(event) => onColumns(event.target.checked ? [...state.columns, field] : state.columns.filter((value) => value !== field))} /> {reportFieldLabel(field)}</label>)}
    </fieldset>
    {views.isLoading ? <LogoLoader label={t`Loading saved views...`} size={48} className="min-h-16 py-3" /> : null}
    <div className="flex flex-wrap gap-2">{views.data?.results?.map((view) => <div key={view.id} className="flex min-w-0 max-w-full flex-wrap items-center gap-2 rounded border border-line p-2">
      <button className="desk-button-ghost min-w-0 break-words text-left" disabled={open.isPending} onClick={() => open.mutate(view.id)}>{view.name}{view.shared ? " (shared)" : ""}</button>
      <button className="desk-button-ghost" disabled={remove.isPending} aria-label={t`Delete ${view.name}`} onClick={() => setDeleting({ id: view.id, name: view.name })}>{t`Delete`}</button>
    </div>)}</div>
    <PagePager page={page} setPage={setPage} next={views.data?.next} />
    {error ? <p role="alert" className="text-sm text-danger">{error instanceof Error ? error.message : t`Could not update saved views.`}</p> : null}
    <ConfirmDialog open={Boolean(deleting)} title={t`Delete saved view`} message={deleting ? t`Delete ${deleting.name}? The saved filters and columns will be removed.` : ""}
      confirmLabel={t`Delete saved view`} tone="danger" pending={remove.isPending} onConfirm={() => deleting && remove.mutate(deleting.id)} onCancel={() => setDeleting(null)} />
  </div>;
}
