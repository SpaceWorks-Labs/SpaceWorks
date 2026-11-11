// Shared print shell: a small persistent queue for print receipts that could not be sent (network down, server
// busy). Receipts hold ids and times only, never names, so localStorage is enough. They are idempotent by
// operation_id, so re-sending after a half-finished flush never double-counts.
import { useEffect } from "react";

import type { PrintReceipt } from "./usePrintReceipts";

const PREFIX = "spaceworks-print-receipts:";
const BATCH = 200;
const read = (key: string): PrintReceipt[] => {
  try { return JSON.parse(localStorage.getItem(PREFIX + key) ?? "[]") as PrintReceipt[]; } catch { return []; }
};
const write = (key: string, items: PrintReceipt[]) => {
  try { if (items.length) localStorage.setItem(PREFIX + key, JSON.stringify(items)); else localStorage.removeItem(PREFIX + key); } catch { /* storage unavailable */ }
};

export async function enqueueReceipt(key: string, receipt: PrintReceipt) {
  const items = read(key);
  if (!items.some((item) => item.operation_id === receipt.operation_id)) write(key, [...items, receipt]);
}

export const queuedReceiptCount = (key: string) => read(key).length;

/** Sends what is queued (at most 200 at a time); keeps it queued if the send fails. Returns how many were sent. */
export async function flushReceiptQueue(key: string, send: (receipts: PrintReceipt[]) => Promise<unknown>) {
  let sent = 0;
  for (let items = read(key); items.length && navigator.onLine; items = read(key)) {
    const batch = items.slice(0, BATCH);
    try { await send(batch); } catch { break; }
    const done = new Set(batch.map((item) => item.operation_id));
    write(key, read(key).filter((item) => !done.has(item.operation_id)));
    sent += batch.length;
  }
  return sent;
}

/** Retries the queue when the page opens and whenever the browser comes back online. */
export function useReceiptQueueFlush(key: string, send: (receipts: PrintReceipt[]) => Promise<unknown>) {
  useEffect(() => {
    const flush = () => { void flushReceiptQueue(key, send); };
    flush();
    window.addEventListener("online", flush);
    return () => window.removeEventListener("online", flush);
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
}
