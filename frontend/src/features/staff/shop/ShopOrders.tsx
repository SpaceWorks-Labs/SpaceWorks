import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ListLayout } from "../../../components/layouts";
import { ListRow, StatusPill } from "../../../components/ui";
import { orderStatus, ORDER_STATUS, shopMoney } from "../../shop/shopApi";
import type { ShopAccess } from "./shopAccess";
import { ShopOrderDetail } from "./ShopOrderDetail";
import { staffShopError, staffShopKeys } from "./staffShopApi";
import { CHANNEL_LABELS, listOrders } from "./staffShopOrdersApi";

/** The order queue: newest first, filtered by status and channel, or found by the buyer's pickup code. */
export function ShopOrders({ makerspaceId, access }: { makerspaceId: number; access: ShopAccess }) {
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [code, setCode] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(null);
  const filters = { status, channel, code: code.trim(), page };
  const query = useQuery({ queryKey: staffShopKeys.orders(makerspaceId, filters), queryFn: () => listOrders(makerspaceId, filters),
    placeholderData: keepPreviousData, enabled: selected === null });
  if (selected !== null) return <ShopOrderDetail makerspaceId={makerspaceId} orderId={selected} access={access} onBack={() => setSelected(null)} />;
  const rows = query.data?.results ?? [];
  const chips = [
    ...(status ? [{ key: "status", label: orderStatus(status).label, onRemove: () => setStatus("") }] : []),
    ...(channel ? [{ key: "channel", label: CHANNEL_LABELS[channel] ?? channel, onRemove: () => setChannel("") }] : []),
  ];
  return <ListLayout header={{ eyebrow: t`Shop`, title: t`Orders`, subtitle: t`Online orders waiting at the desk, and every desk sale.` }}
    state={query.isPending ? { status: "loading" } : query.error ? { status: "error", error: staffShopError(query.error),
      onRetry: () => { void query.refetch(); } } : { status: "ready" }}
    filters={{ search: { label: t`Pickup code`, placeholder: t`Find by pickup code`, value: code, onChange: next => { setCode(next.toUpperCase()); setPage(1); } },
      chips, activeCount: chips.length, onClear: () => { setStatus(""); setChannel(""); setPage(1); },
      controls: <div className="grid gap-3">
        <label className="grid gap-1 text-sm font-semibold">{t`Status`}<select className="desk-input min-h-11 font-normal" value={status}
          onChange={event => { setStatus(event.target.value); setPage(1); }}>
          <option value="">{t`Any status`}</option>
          {Object.entries(ORDER_STATUS).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</select></label>
        <label className="grid gap-1 text-sm font-semibold">{t`Channel`}<select className="desk-input min-h-11 font-normal" value={channel}
          onChange={event => { setChannel(event.target.value); setPage(1); }}>
          <option value="">{t`Online and desk`}</option>
          {Object.entries(CHANNEL_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      </div> }}
    filtered={Boolean(status || channel || code.trim())}
    isEmpty={!rows.length} empty={{ message: t`No shop orders yet.` }} filteredEmpty={{ message: t`No orders match these filters.` }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: rows.map(order => {
      const label = orderStatus(order.status ?? "");
      const buyer = order.buyer_name || order.guest_name || (order.channel === "pos" ? "Walk-in" : "Guest");
      return <ListRow key={order.id} title={`#${order.id} · ${buyer}`} identity={{ kind: "code", code: order.pickup_code || "—" }}
        meta={<span className="text-sm text-muted">{CHANNEL_LABELS[order.channel ?? ""] ?? order.channel} · {shopMoney(order.total, order.currency)} · {new Date(order.created_at).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" })}</span>}
        right={<StatusPill label={label.label} tone={label.tone} />} onClick={() => setSelected(order.id)} />;
    }) }} />;
}
