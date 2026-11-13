import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, ConfirmDialog, PagePager } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { communicationKeys } from "../eventCommunicationsApi";
import type { Paginated } from "../eventsApiTypes";
import { eventErrorText } from "../eventUi";
import { BroadcastComposer } from "./BroadcastComposer";
import { BroadcastDeliveryControls } from "./BroadcastDeliveryControls";
import { broadcastStatusLabel, type BroadcastCampaign, type BroadcastDraft } from "./broadcastApi";
import { sessionScope, useClearDeniedQuery } from "./sessionScope";
import { LogoLoader } from "../../../components/LogoLoader";

export function EventBroadcastsPanel({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const [page, setPage] = useState(1);
  const [seed, setSeed] = useState<{ revision: number; value?: BroadcastDraft; existing?: BroadcastCampaign }>({ revision: 0 });
  const [selected, setSelected] = useState<BroadcastCampaign | null>(null);
  const [reuse, setReuse] = useState<BroadcastDraft | null>(null);
  const opened = useRef(false);
  const key = [...communicationKeys.campaigns(makerspaceId, eventId), page, ...sessionScope()];
  const history = useQuery({ queryKey: key, queryFn: () => staffRequest<Paginated<BroadcastCampaign>>(`/admin/events/${eventId}/broadcasts/?page=${page}`), refetchInterval: query => query.state.data?.results.some(row => ["scheduled", "queued", "sending"].includes(row.status)) ? 5000 : false });
  const current = selected ? history.data?.results.find(row => row.id === selected.id) ?? selected : null;
  const denied = useClearDeniedQuery(history.error, key);
  // Drafts are private to their author, so any composer draft listed here is the viewer's own; it opens by itself.
  const ownDraft = history.data?.results.find(row => row.status === "draft" && row.render_schema_version === 2);
  useEffect(() => {
    if (opened.current || !history.data || page !== 1) return;
    opened.current = true;
    if (ownDraft) setSeed(value => value.revision ? value : { revision: value.revision + 1, existing: ownDraft });
  }, [history.data, page, ownDraft]);
  const startReuse = (value: BroadcastDraft) => { setReuse(null); setSeed({ revision: seed.revision + 1, value, existing: ownDraft }); };
  useEffect(() => { if (denied) { setSelected(null); setSeed({ revision: 0 }); } }, [denied]);
  if (denied) return <p role="alert" className="text-sm text-danger">{t`Broadcasts are no longer available for your access.`}</p>;
  return <section className="grid gap-4" aria-label={t`Event broadcasts`}><div><h3 className="title-section">{t`Email registrants`}</h3><p className="mt-1 text-sm text-muted">{t`Drafts save as you type. Preview, test, then send with a five-second undo or schedule it. Verified email, preferences and quiet hours apply. Accepted email cannot be recalled.`}</p></div>
    <BroadcastComposer key={seed.revision} initial={seed.value} existing={seed.existing} makerspaceId={makerspaceId} eventId={eventId} onSaved={row => { setSelected(row); setPage(1); }} onDiscarded={() => setSelected(null)} />
    {current ? <Card><h4 className="mb-3 font-semibold">{current.subject}</h4><BroadcastDeliveryControls key={`${current.id}-${current.version}`} campaign={current} makerspaceId={makerspaceId} eventId={eventId} /></Card> : null}
    {history.isLoading ? <LogoLoader size={48} className="min-h-24 py-3" /> : null}{history.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(history.error)}</p> : null}
    <ul className="grid gap-3" aria-label={t`Sent and draft broadcasts`}>{history.data?.results.map(row => <li key={row.id} className="grid gap-3 rounded-2xl border border-line bg-panel p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold">{row.subject}</h4><span className="rounded-full bg-surface px-3 py-1 text-xs">{broadcastStatusLabel(row.status)}</span></div>{row.available_at ? <p className="text-sm text-muted">{t`Scheduled: ${new Date(row.available_at).toLocaleString(formatLocale())}`}</p> : null}<div className="flex flex-wrap gap-2"><button className="desk-button" type="button" onClick={() => setSelected(row)}>{t`Open broadcast`}</button>{row.status === "draft" && row.render_schema_version === 2 ? <button className="desk-button" type="button" onClick={() => { setSeed({ revision: seed.revision + 1, existing: row }); setSelected(row); }}>{t`Continue editing`}</button> : null}<button className="desk-button" type="button" onClick={() => { const value: BroadcastDraft = { subject: row.subject, body: row.body, statuses: row.statuses, attendance: row.attendance, render_schema_version: 2, design: row.design ?? "classic", ctas: row.ctas ?? [] }; if (ownDraft && ownDraft.id !== row.id) setReuse(value); else startReuse(value); }}>{t`Reuse message`}</button></div></li>)}</ul>
    {history.data?.count === 0 ? <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">{t`No broadcasts yet.`}</p> : null}
    <PagePager page={page} setPage={setPage} next={history.data?.next} />
    <ConfirmDialog open={reuse !== null} title={t`Replace your draft?`} message={t`Reusing this email replaces what you have written in your open draft.`}
      confirmLabel={t`Replace draft`} cancelLabel={t`Keep my draft`} onCancel={() => setReuse(null)} onConfirm={() => { if (reuse) startReuse(reuse); }} />
  </section>;
}
