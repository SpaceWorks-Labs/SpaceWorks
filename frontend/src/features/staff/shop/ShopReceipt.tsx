import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { DetailLayout } from "../../../components/layouts";
import { Field, SegmentedControl } from "../../../components/ui";
import { readStorage, writeStorage } from "../../../lib/safeStorage";
import "./shopReceipt.css";
import { ShopReceiptDocument, type PaperFormat } from "./ShopReceiptDocument";
import { staffShopError } from "./staffShopApi";
import { emailReceipt, fetchReceipt } from "./staffShopOrdersApi";

const FORMAT_KEY = "spaceworks.shop.receiptFormat";
/** One explicit @page rule per format: a continuous 80 mm roll, or an A4 sheet with normal margins. */
export const PAGE_RULES: Record<PaperFormat, string> = {
  "80mm": "@page { size: 80mm auto; margin: 3mm 4mm; }",
  a4: "@page { size: A4 portrait; margin: 15mm; }",
};

/** The receipt on screen, printable on an 80 mm till printer or A4 paper, and sent by email. */
export function ShopReceipt({ orderId, onBack }: { orderId: number; onBack: () => void }) {
  const [format, setFormat] = useState<PaperFormat>(() => readStorage(FORMAT_KEY) === "a4" ? "a4" : "80mm");
  const [email, setEmail] = useState("");
  const query = useQuery({ queryKey: ["staff-shop-receipt", orderId], queryFn: () => fetchReceipt(orderId) });
  const send = useMutation({ mutationFn: () => emailReceipt(orderId, email.trim()) });
  const choose = (next: PaperFormat) => { setFormat(next); writeStorage(FORMAT_KEY, next); };
  return <DetailLayout back={{ label: "Back to the order", onClick: onBack }} title={query.data?.document_title || "Receipt"}
    meta={[`Order #${orderId}`]}
    state={query.isPending ? { status: "loading" } : query.error ? { status: "error", error: staffShopError(query.error),
      onRetry: () => { void query.refetch(); } } : { status: "ready" }}
    actions={{ primary: { label: format === "80mm" ? "Print 80 mm receipt" : "Print A4", icon: "Printer", onClick: () => window.print() } }}
    main={query.data ? <div className="grid gap-5">
      <style data-receipt-page={format}>{PAGE_RULES[format]}</style>
      <div className="shop-receipt-no-print grid gap-2">
        <SegmentedControl label="Paper size" value={format} onChange={value => choose(value as PaperFormat)}
          options={[{ value: "80mm", label: "80 mm till roll" }, { value: "a4", label: "A4 sheet" }]} />
      </div>
      <ShopReceiptDocument receipt={query.data} format={format} />
    </div> : null}
    aside={query.data ? <form className="shop-receipt-no-print grid gap-3" onSubmit={event => { event.preventDefault(); send.mutate(); }}>
      <h2 className="title-section">Email the receipt</h2>
      <Field label="Email" hint="Leave empty to send it to the buyer's email on the order.">
        <input className="desk-input min-h-11" type="email" value={email} onChange={event => { setEmail(event.target.value); send.reset(); }} /></Field>
      <button type="submit" className="desk-button min-h-11 justify-self-start" disabled={send.isPending}>{send.isPending ? "Sending…" : "Send receipt"}</button>
      <p role="status" className="text-sm text-muted">{send.isSuccess ? "Receipt sent." : ""}</p>
      {send.error ? <p role="alert" className="text-sm text-danger">{staffShopError(send.error)}</p> : null}
    </form> : undefined} />;
}
