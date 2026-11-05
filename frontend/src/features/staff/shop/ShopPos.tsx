import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "../../../components/ui";
import { ShopCartLines } from "../../shop/ShopCartLines";
import { ShopQuoteSummary } from "../../shop/ShopQuoteSummary";
import type { CartLine } from "../../shop/useShopCart";
import { PosMemberPicker, type TillMember } from "./PosMemberPicker";
import { paymentReady, PosPayment, type TillPayment } from "./PosPayment";
import { PosScanInput, type TillItem } from "./PosScanInput";
import type { ShopAccess } from "./shopAccess";
import { ShopReceipt } from "./ShopReceipt";
import { errorCode, listAllProducts, staffShopError, staffShopKeys } from "./staffShopApi";
import { posQuote, posSale, type ShopStaffOrder } from "./staffShopOrdersApi";

const fresh: TillPayment = { method: "cash", reference: "", email: "" };

/** The desk till: scan or type, adjust the basket, price it live on the server, take payment, print the receipt. No effects. */
export function ShopPos({ makerspaceId, access }: { makerspaceId: number; access: ShopAccess }) {
  const client = useQueryClient();
  const scan = useRef<HTMLInputElement>(null);
  const [lines, setLines] = useState<CartLine[]>([]);
  const [member, setMember] = useState<TillMember | null>(null);
  const [payment, setPayment] = useState<TillPayment>(fresh);
  const [sold, setSold] = useState<ShopStaffOrder | null>(null);
  const catalogue = useQuery({ queryKey: staffShopKeys.allProducts(makerspaceId), queryFn: () => listAllProducts(makerspaceId) });
  const items = useMemo<TillItem[]>(() => (catalogue.data ?? []).filter(product => product.is_active !== false)
    .flatMap(product => (product.variants ?? []).filter(variant => variant.id && variant.is_active !== false && !variant.archived_at)
      .map(variant => ({ variantId: variant.id as number, sku: variant.sku ?? "", price: variant.price, available: variant.available,
        max: product.max_per_order ?? null,
        label: (product.variants?.length ?? 0) > 1 && variant.name ? `${product.name} · ${variant.name}` : product.name }))), [catalogue.data]);
  const request = lines.map(line => ({ variant_id: line.variantId, quantity: line.quantity }));
  const quote = useQuery({ queryKey: ["staff-shop", makerspaceId, "pos-quote", request, member?.id ?? null],
    queryFn: () => posQuote(makerspaceId, request, member?.id ?? null), enabled: request.length > 0 && !sold, retry: false });
  useEffect(() => { if (!sold) scan.current?.focus(); }, [sold]);
  const sell = useMutation({
    mutationFn: () => posSale(makerspaceId, { lines: request, member_id: member?.id ?? null, method: payment.method,
      reference: payment.reference.trim(), quote_digest: quote.data?.digest ?? "",
      ...(payment.email.trim() ? { receipt_email: payment.email.trim() } : {}) }),
    onSuccess: order => {
      setSold(order);
      void client.invalidateQueries({ queryKey: staffShopKeys.all(makerspaceId) });
    },
    onError: error => { if (errorCode(error) === "price_changed") void quote.refetch(); },
  });
  const add = (item: TillItem) => setLines(current => {
    const found = current.find(line => line.variantId === item.variantId);
    if (found) return current.map(line => line.variantId === item.variantId ? { ...line, quantity: line.quantity + 1 } : line);
    return [...current, { variantId: item.variantId, quantity: 1, label: item.label, price: item.price, productSlug: "", max: item.max }];
  });
  const reset = () => { setLines([]); setMember(null); setPayment(fresh); setSold(null); sell.reset(); };
  if (sold) return access.features.receipts ? <div className="grid gap-4">
    <p role="status" className="title-section">Sale recorded: order #{sold.id}.</p>
    <button type="button" className="desk-button-primary min-h-14 justify-self-start px-6 text-lg" onClick={reset}>Start a new sale</button>
    <ShopReceipt orderId={sold.id} onBack={reset} />
  </div> : <div className="grid gap-4"><p role="status" className="title-section">Sale recorded: order #{sold.id}.</p>
    <button type="button" className="desk-button-primary min-h-14 justify-self-start px-6 text-lg" onClick={reset}>Start a new sale</button></div>;
  const canSell = lines.length > 0 && Boolean(quote.data) && !quote.isFetching && paymentReady(payment);
  return <section aria-label="Till" className="grid min-w-0 gap-6">
    <PageHeader eyebrow="Shop" title="Till" subtitle="Scan or type an item and press Enter. Prices and discounts come from the server." />
    <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,26rem)]">
      <div className="grid min-w-0 content-start gap-5">
        {catalogue.error ? <p role="alert" className="text-sm text-danger">{staffShopError(catalogue.error)}</p> : null}
        <PosScanInput ref={scan} items={items} onAdd={add} disabled={catalogue.isPending} />
        <ShopCartLines lines={lines} currency={quote.data?.currency ?? "inr"} disabled={sell.isPending}
          onQuantity={(id, quantity) => setLines(current => current.map(line => line.variantId === id ? { ...line, quantity } : line).filter(line => line.quantity > 0))}
          onRemove={id => setLines(current => current.filter(line => line.variantId !== id))} />
        {access.features.memberPrices ? <PosMemberPicker makerspaceId={makerspaceId} member={member} onChange={setMember} /> : null}
      </div>
      <aside aria-label="Payment" className="grid min-w-0 content-start gap-4 rounded-xl border border-line bg-panel p-4">
        {quote.isFetching && !quote.data ? <p role="status" className="text-sm text-muted">Pricing…</p> : null}
        {quote.error ? <p role="alert" className="text-sm text-danger">{staffShopError(quote.error)}</p> : null}
        {quote.data && lines.length ? <ShopQuoteSummary quote={quote.data} title="Sale" /> : <p className="text-sm text-muted">The basket is empty.</p>}
        <PosPayment value={payment} onChange={setPayment} receipts={access.features.receipts} />
        {sell.error ? <p role="alert" className="text-sm text-danger">{staffShopError(sell.error)}</p> : null}
        <button type="button" className="desk-button-primary min-h-14 w-full text-lg" disabled={!canSell || sell.isPending} onClick={() => sell.mutate()}>
          {sell.isPending ? "Recording sale…" : "Sell"}</button>
        {lines.length ? <button type="button" className="desk-button min-h-11" disabled={sell.isPending} onClick={reset}>Clear the basket</button> : null}
      </aside>
    </div>
  </section>;
}
