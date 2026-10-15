import { useEffect, useState, type FormEvent } from "react";

import { ConfirmDialog, ListRow, Skeleton, StatusBadge } from "../../components/ui";
import { DetailLayout } from "../../components/layouts";
import { opsQueryState, useOpsTabs, opsStatusLabel } from "./opsPresentation";
import { EventSeriesCollaborators } from "./EventSeriesCollaborators";
import { ImageUploader } from "./ImageUploader";
import { EventSeriesFields, emptySeriesForm, seriesPayload, valuesForSeries } from "./EventSeriesForm";
import {
  useEventSeries,
  useEventSeriesAction,
  useEventSeriesOccurrences,
  useUpdateEventSeries,
} from "./eventSeriesApi";
import { eventErrorText } from "./eventUi";

type Action = "publish" | "cancel" | "complete" | "extend";

export function EventSeriesDrawer({ seriesId, makerspaceId, onClose, onSelectOccurrence }: {
  seriesId: number; makerspaceId: number; onClose: () => void;
  onSelectOccurrence: (eventId: number) => void;
}) {
  const query = useEventSeries(seriesId);
  const occurrences = useEventSeriesOccurrences(seriesId);
  const update = useUpdateEventSeries(makerspaceId, seriesId);
  const [values, setValues] = useState(emptySeriesForm);
  const [confirm, setConfirm] = useState<Action | null>(null);
  const publish = useEventSeriesAction(makerspaceId, seriesId, "publish");
  const cancel = useEventSeriesAction(makerspaceId, seriesId, "cancel");
  const complete = useEventSeriesAction(makerspaceId, seriesId, "complete");
  const extend = useEventSeriesAction(makerspaceId, seriesId, "extend");
  const action = confirm === "publish" ? publish : confirm === "cancel" ? cancel : confirm === "complete" ? complete : extend;
  useEffect(() => { if (query.data) setValues(valuesForSeries(query.data)); }, [query.data?.updated_at]);
  const terminal = query.data?.status === "cancelled" || query.data?.status === "completed";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const payload = seriesPayload(values);
    update.mutate({ ...payload, ...(query.data?.status === "published" ? { effective_from: new Date().toISOString() } : {}) });
  };
  const tabs = useOpsTabs("seriesTab", [{ key: "occurrences", label: "Occurrences", count: occurrences.data?.count }, { key: "team", label: "Team" }, { key: "settings", label: "Settings" }], "occurrences");
  return <>
    <div onClickCapture={tabs.onClickCapture}><DetailLayout title={query.data?.title ?? "Recurring series"} back={{ label: "All events", onClick: onClose }}
      identity={{ kind: "icon", icon: "Calendar", tone: "accent" }}
      status={query.data ? <StatusBadge domain="event" status={query.data.status} label={opsStatusLabel(query.data.status)} /> : undefined}
      meta={query.data ? [`${query.data.future_occurrence_count} active occurrences`, `Revision ${query.data.revision}`] : undefined}
      state={opsQueryState(query, "series")} tabs={tabs.tabs} activeTab={tabs.active}
      actions={{ primary: query.data?.status === "draft" ? { label: "Publish series", confirms: true, onClick: () => setConfirm("publish") } : query.data?.status === "published" ? { label: "Extend now", onClick: () => setConfirm("extend") } : undefined,
        overflow: query.data?.status === "published" ? [{ label: "Complete series", confirms: true, onClick: () => setConfirm("complete") },
          { label: "Cancel series", confirms: true, tone: "danger", onClick: () => setConfirm("cancel") }] : undefined }}
      banner={query.data?.last_generation_error_code ? { size: "banner", tone: "danger", lead: `Automatic extension needs attention (${query.data.last_generation_error_code}).`,
        body: "Correct the schedule in Settings, then use Extend now.", action: query.data.status === "published" ? { label: "Extend now", onClick: () => setConfirm("extend") } : undefined } : undefined}
      danger={tabs.active === "settings" && query.data?.status === "published" ? [{ title: "Cancel series", consequence: "Future occurrences close and registrants are notified.", action: { label: "Cancel series", onClick: () => setConfirm("cancel") } }] : []}
      main={query.data ? <div className="grid gap-5">
        {tabs.active === "settings" ? <div className="grid gap-5">
        <ImageUploader endpoint={`/admin/event-series/${seriesId}/image`} currentUrl={query.data.image_url} label="Series photo (inherited by occurrences)" shape="wide" disabled={terminal} onChanged={() => query.refetch()} />
        <form onSubmit={submit}><h3 className="title-section mb-3">Edit future occurrences</h3><EventSeriesFields values={values} setValues={setValues} disabled={terminal} />{!terminal ? <div className="sticky bottom-0 flex justify-end gap-3 border-t border-line bg-panel py-4"><button className="desk-button" type="button" disabled={update.isPending} onClick={() => setValues(valuesForSeries(query.data!))}>Discard</button><button className="desk-button-primary" type="submit" disabled={update.isPending}>Save future occurrences</button></div> : null}</form>
        {query.data.status === "published" ? <button className="desk-button justify-self-start" type="button" onClick={() => setConfirm("complete")}>Complete series</button> : null}
        </div> : null}
        {update.error || action.error ? <p className="text-sm text-danger" role="alert">{eventErrorText(update.error || action.error)}</p> : null}
        {tabs.active === "occurrences" ? <section><h2 className="title-panel">Occurrences</h2><p className="mt-1 text-sm text-muted">Choose a date to edit or cancel only that occurrence.</p>
          {occurrences.isLoading ? <Skeleton className="mt-3 h-24 w-full" /> : null}
          <div className="mt-3 grid gap-3">{occurrences.data?.results.map(row => <ListRow key={row.id} title={new Date(row.starts_at).toLocaleString()} identity={{ kind: "date", date: row.starts_at }} draft={row.status === "draft"} onClick={() => onSelectOccurrence(row.id)} right={<StatusBadge domain="event" status={row.status} label={opsStatusLabel(row.status)} />} />)}</div>
        </section> : null}
        <EventSeriesCollaborators visible={tabs.active === "team"} seriesId={seriesId} makerspaceId={makerspaceId} />
      </div> : null} /></div>
    <ConfirmDialog open={confirm !== null} title={`${confirm ?? "Change"} recurring series`} message={`This will ${confirm ?? "change"} the series and its applicable occurrences.`} confirmLabel="Confirm" tone={confirm === "cancel" ? "danger" : "default"} pending={action.isPending} onCancel={() => setConfirm(null)} onConfirm={() => action.mutate(undefined, { onSettled: () => setConfirm(null) })} />
  </>;
}
