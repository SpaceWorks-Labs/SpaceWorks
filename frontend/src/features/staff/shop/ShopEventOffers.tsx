import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { ListLayout } from "../../../components/layouts";
import { staffRequest } from "../../../lib/api";
import { listAllProducts, staffShopError, staffShopKeys } from "./staffShopApi";

/** Hand-typed until the client is regenerated (#135 Q-S18 follow-up). */
export type ShopEventOfferRow = { id: number; title: string; starts_at: string; status: string; variant_ids: number[] };

const base = (ms: number) => `/admin/makerspaces/${ms}/shop/event-offers/`;
const offersKey = (ms: number) => ["staff-shop", ms, "event-offers"] as const;

/**
 * Pick which shop items an upcoming event offers on its page. Buyers order them as normal
 * shop orders collected at the event; registration and its charge are never touched.
 */
export function ShopEventOffers({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const events = useQuery({ queryKey: offersKey(makerspaceId), queryFn: () => staffRequest<ShopEventOfferRow[]>(base(makerspaceId)) });
  const products = useQuery({ queryKey: staffShopKeys.allProducts(makerspaceId), queryFn: () => listAllProducts(makerspaceId) });
  const [chosenEvent, setChosenEvent] = useState<number | null>(null);
  const [draft, setDraft] = useState<{ eventId: number; ids: number[] } | null>(null);
  const eventId = chosenEvent ?? events.data?.[0]?.id ?? null;
  const saved = events.data?.find(row => row.id === eventId)?.variant_ids ?? [];
  const selected = draft?.eventId === eventId ? draft.ids : saved;
  const variants = useMemo(() => (products.data ?? []).filter(product => product.is_active !== false && !product.archived_at)
    .flatMap(product => (product.variants ?? []).filter(variant => variant.id && variant.is_active !== false && !variant.archived_at)
      .map(variant => ({ id: variant.id as number,
        label: (product.variants?.length ?? 0) > 1 ? `${product.name} · ${variant.name}` : product.name }))), [products.data]);
  const save = useMutation({
    mutationFn: () => staffRequest<{ variant_ids: number[] }>(`${base(makerspaceId)}${eventId}/`,
      { method: "PUT", body: JSON.stringify({ variant_ids: selected }) }),
    onSuccess: () => { setDraft(null); void client.invalidateQueries({ queryKey: offersKey(makerspaceId) }); },
  });
  const toggle = (id: number) => {
    if (eventId === null) return;
    setDraft({ eventId, ids: selected.includes(id) ? selected.filter(value => value !== id) : [...selected, id] });
  };
  const error = events.error ?? products.error;
  return <ListLayout header={{ eyebrow: t`Shop`, title: t`Event merch`,
    subtitle: t`Show shop items on an event's page. Buyers order them separately and collect them at the event.` }}
    state={events.isPending || products.isPending ? { status: "loading" } : error ? { status: "error", error: staffShopError(error),
      onRetry: () => { void events.refetch(); void products.refetch(); } } : { status: "ready" }}
    isEmpty={!events.data?.length} empty={{ message: t`No upcoming events. Event merch can be set once an event is scheduled.` }}
    body={{ kind: "rows", rows: [<div key="event-offers" className="grid gap-4">
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Event`}
        <select className="desk-input min-h-11 font-normal" value={eventId ?? ""} onChange={event => { save.reset(); setChosenEvent(Number(event.target.value)); }}>
          {(events.data ?? []).map(row => <option key={row.id} value={row.id}>
            {`${row.title} (${new Date(row.starts_at).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" })})`}</option>)}
        </select></label>
      <fieldset className="grid gap-2">
        <legend className="text-sm font-semibold text-ink">{t`Items offered at this event`}</legend>
        {variants.length ? variants.map(row => <label key={row.id} className="flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" checked={selected.includes(row.id)} onChange={() => toggle(row.id)} />{row.label}</label>)
          : <p className="text-sm text-muted">{t`Add products to the catalogue first.`}</p>}
      </fieldset>
      {save.error ? <p role="alert" className="text-sm text-danger">{staffShopError(save.error)}</p> : null}
      {save.isSuccess ? <p role="status" className="text-sm text-muted">{t`Event merch saved.`}</p> : null}
      <button type="button" className="desk-button-primary min-h-11 justify-self-start" disabled={eventId === null || save.isPending}
        onClick={() => save.mutate()}>{save.isPending ? t`Saving…` : t`Save event merch`}</button>
    </div>] }} />;
}
