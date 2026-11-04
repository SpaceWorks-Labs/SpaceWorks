import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { FlowLayout, type FlowStep } from "../../../components/layouts";
import { Field } from "../../../components/ui";
import { shopMoney } from "../../shop/shopApi";
import { staffShopError, staffShopKeys } from "./staffShopApi";
import { closeCash, confirmCash, listCashSessions, openCash, type ShopCashSession } from "./staffShopOrdersApi";

const amount = (value: string) => /^\d+(\.\d{1,2})?$/.test(value.trim());
function varianceText(session: ShopCashSession) {
  const value = Number(session.variance ?? 0);
  const money = shopMoney(Math.abs(value), session.currency);
  return value === 0 ? "Balanced" : value > 0 ? `${money} over` : `${money} short`;
}

/** Cash-up: open the drawer with a float, close it with the counted cash, and a second person confirms the count. */
export function ShopCashUp({ makerspaceId, canManage, onLeave }: { makerspaceId: number; canManage: boolean; onLeave: () => void }) {
  const client = useQueryClient();
  const [float, setFloat] = useState("");
  const [counted, setCounted] = useState("");
  const [note, setNote] = useState("");
  const [finished, setFinished] = useState<ShopCashSession | null>(null);
  const query = useQuery({ queryKey: staffShopKeys.cash(makerspaceId), queryFn: () => listCashSessions(makerspaceId) });
  const current = query.data?.results.find(row => row.status === "open" || row.status === "closing") ?? null;
  const settle = (session: ShopCashSession) => {
    if (session.status === "closed") setFinished(session);
    void client.invalidateQueries({ queryKey: staffShopKeys.cash(makerspaceId) });
  };
  const open = useMutation({ mutationFn: () => openCash(makerspaceId, float.trim()), onSuccess: settle });
  const close = useMutation({ mutationFn: () => closeCash(current!.id, counted.trim(), note.trim()), onSuccess: settle });
  const confirm = useMutation({ mutationFn: () => confirmCash(current!.id), onSuccess: settle });
  const step = !current ? "open" : current.status === "open" ? "count" : "confirm";
  const steps: FlowStep[] = [
    { key: "open", label: "Open the drawer", state: step === "open" ? "current" : "done" },
    { key: "count", label: "Count the cash", state: step === "count" ? "current" : step === "confirm" ? "done" : "todo" },
    { key: "confirm", label: "Second person confirms", state: step === "confirm" ? "current" : "todo" },
  ];
  const error = open.error ?? close.error ?? confirm.error;
  const money = (value: string | null | undefined) => shopMoney(value ?? 0, current?.currency ?? finished?.currency ?? "inr");
  const work = step === "open" ? <div className="grid gap-4">
    <p>Count the notes and coins you start the day with and enter the total.</p>
    <Field label="Opening float"><input className="desk-input min-h-11 tabular-nums" inputMode="decimal" value={float}
      onChange={event => setFloat(event.target.value)} /></Field>
  </div> : current ? <div className="grid gap-4">
    <dl className="grid gap-2 sm:grid-cols-2">
      <div><dt className="text-sm text-muted">Opening float</dt><dd className="text-lg font-semibold tabular-nums">{money(current.opening_float)}</dd></div>
      <div><dt className="text-sm text-muted">Expected in the drawer now</dt><dd className="text-lg font-semibold tabular-nums">
        {money(current.status === "closing" ? current.expected_cash : current.expected_now)}</dd></div>
      {current.status === "closing" ? <>
        <div><dt className="text-sm text-muted">Counted</dt><dd className="text-lg font-semibold tabular-nums">{money(current.counted_cash)}</dd></div>
        <div><dt className="text-sm text-muted">Variance</dt><dd className="text-lg font-semibold tabular-nums">{varianceText(current)}</dd></div>
      </> : null}
    </dl>
    {current.status === "open" ? <>
      <Field label="Counted cash" hint="Everything in the drawer, float included."><input className="desk-input min-h-11 tabular-nums"
        inputMode="decimal" value={counted} onChange={event => setCounted(event.target.value)} /></Field>
      <Field label="Note (optional)" hint="Explain any difference."><textarea className="desk-input" rows={2} value={note}
        onChange={event => setNote(event.target.value)} /></Field>
    </> : <p>{current.note ? `Note: ${current.note}. ` : ""}A different staff member checks the count and confirms it.{canManage ? "" : " You cannot confirm your own count."}</p>}
  </div> : null;
  const next = step === "open"
    ? { label: "Open the drawer", onClick: () => open.mutate(), pending: open.isPending, disabled: !amount(float), disabledReason: amount(float) ? undefined : "Enter the opening float." }
    : step === "count"
      ? { label: "Close and record the count", onClick: () => close.mutate(), pending: close.isPending, disabled: !amount(counted), disabledReason: amount(counted) ? undefined : "Enter the counted cash." }
      : { label: "Confirm the count", onClick: () => confirm.mutate(), pending: confirm.isPending };
  return <FlowLayout standalone={false} title="Cash-up" subject="The front-desk cash drawer for shop sales." steps={steps} current={step}
    state={query.isPending ? { status: "loading" } : query.error ? { status: "error", error: staffShopError(query.error),
      onRetry: () => { void query.refetch(); } } : { status: "ready" }}
    work={work} footer={{ next }} onCancel={onLeave}
    error={error ? { size: "inline", tone: "danger", lead: staffShopError(error) } : undefined}
    result={finished ? { tone: Number(finished.variance ?? 0) === 0 ? "success" : "warn", title: "Drawer closed",
      summary: <p>Expected {money(finished.expected_cash)}, counted {money(finished.counted_cash)}: {varianceText(finished)}.</p>,
      next: { label: "Open a new drawer", onClick: () => { setFinished(null); setFloat(""); setCounted(""); setNote(""); } } } : undefined} />;
}
