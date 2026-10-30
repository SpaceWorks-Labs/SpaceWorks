import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, Skeleton } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { communicationKeys } from "../eventCommunicationsApi";
import type { Paginated } from "../eventsApiTypes";
import { eventErrorText } from "../eventUi";
import { BroadcastComposer } from "./BroadcastComposer";
import { BroadcastDeliveryControls } from "./BroadcastDeliveryControls";
import type { BroadcastCampaign, BroadcastDraft } from "./broadcastApi";
import { sessionScope, useClearDeniedQuery } from "./sessionScope";

export function EventBroadcastsPanel({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const [page, setPage] = useState(1);
  const [seed, setSeed] = useState<{ revision: number; value?: BroadcastDraft; existing?: BroadcastCampaign }>({ revision: 0 });
  const [selected, setSelected] = useState<BroadcastCampaign | null>(null);
  const key = [...communicationKeys.campaigns(makerspaceId, eventId), page, ...sessionScope()];
  const history = useQuery({ queryKey: key, queryFn: () => staffRequest<Paginated<BroadcastCampaign>>(`/admin/events/${eventId}/broadcasts/?page=${page}`), refetchInterval: query => query.state.data?.results.some(row => ["scheduled", "queued", "sending"].includes(row.status)) ? 5000 : false });
  const current = selected ? history.data?.results.find(row => row.id === selected.id) ?? selected : null;
  const denied = useClearDeniedQuery(history.error, key);
  useEffect(() => { if (denied) { setSelected(null); setSeed({ revision: 0 }); } }, [denied]);
  if (denied) return <p role="alert" className="text-sm text-danger">Broadcasts are no longer available for your access.</p>;
  return <section className="grid gap-4" aria-label="Event broadcasts"><div><h3 className="title-section">Email registrants</h3><p className="mt-1 text-sm text-muted">Drafts save as you type. Preview, test, then send with a five-second undo or schedule it. Verified email, preferences and quiet hours apply. Accepted email cannot be recalled.</p></div>
    <BroadcastComposer key={seed.revision} initial={seed.value} existing={seed.existing} makerspaceId={makerspaceId} eventId={eventId} onSaved={row => { setSelected(row); setPage(1); }} />
    {current ? <Card><h4 className="mb-3 font-semibold">{current.subject}</h4><BroadcastDeliveryControls key={`${current.id}-${current.version}`} campaign={current} makerspaceId={makerspaceId} eventId={eventId} /></Card> : null}
    {history.isLoading ? <Skeleton className="h-24 w-full" /> : null}{history.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(history.error)}</p> : null}
    <ul className="grid gap-3" aria-label="Sent and draft broadcasts">{history.data?.results.map(row => <li key={row.id} className="grid gap-3 rounded-2xl border border-line bg-panel p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold">{row.subject}</h4><span className="rounded-full bg-surface px-3 py-1 text-xs">{row.status.replace(/_/g, " ")}</span></div>{row.available_at ? <p className="text-sm text-muted">Scheduled: {new Date(row.available_at).toLocaleString()}</p> : null}<div className="flex flex-wrap gap-2"><button className="desk-button" type="button" onClick={() => setSelected(row)}>Open broadcast</button>{row.status === "draft" && row.render_schema_version === 2 ? <button className="desk-button" type="button" onClick={() => { setSeed({ revision: seed.revision + 1, existing: row }); setSelected(row); }}>Continue editing</button> : null}<button className="desk-button" type="button" onClick={() => setSeed({ revision: seed.revision + 1, value: { subject: row.subject, body: row.body, statuses: row.statuses, attendance: row.attendance, render_schema_version: 2, design: row.design ?? "classic", ctas: row.ctas ?? [] } })}>Reuse message</button></div></li>)}</ul>
    {history.data?.count === 0 ? <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">No broadcasts yet.</p> : null}
    {history.data?.next || history.data?.previous ? <nav className="flex items-center justify-end gap-2" aria-label="Broadcast pages"><button className="desk-button" disabled={!history.data.previous} onClick={() => setPage(page - 1)}>Previous broadcasts</button><span className="text-sm">Page {page}</span><button className="desk-button" disabled={!history.data.next} onClick={() => setPage(page + 1)}>Next broadcasts</button></nav> : null}
  </section>;
}
