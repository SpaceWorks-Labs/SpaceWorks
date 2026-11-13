// Shared print shell: records that a card was printed. Each receipt gets a fresh uuid (`operation_id`) so the
// server can de-duplicate a retry. Online it is sent at once; when the network is down or the call fails, the
// caller's `queue` stores it (the encrypted offline store) to be sent with the next sync. The hook keeps
// nothing itself.
import { useCallback, useState } from "react";

export type PrintReceipt<Extra extends object = object> = Extra & { operation_id: string; printed_at: string };
export type ReceiptOutcome = "sent" | "queued" | "lost";

export function newReceipt<Extra extends object>(extra: Extra): PrintReceipt<Extra> {
  return { ...extra, operation_id: crypto.randomUUID(), printed_at: new Date().toISOString() };
}

export function usePrintReceipts<Extra extends object>({ send, queue }: {
  /** Sends one receipt now; omit when there is no online path (offline desks, stations). */
  send?: (receipt: PrintReceipt<Extra>) => Promise<unknown>;
  /** Stores a receipt for the next sync. */
  queue?: (receipt: PrintReceipt<Extra>) => Promise<unknown>;
}) {
  const [last, setLast] = useState<ReceiptOutcome | null>(null);
  const record = useCallback(async (extra: Extra): Promise<ReceiptOutcome> => {
    const receipt = newReceipt(extra);
    let outcome: ReceiptOutcome = "lost";
    if (send && navigator.onLine) {
      try { await send(receipt); outcome = "sent"; } catch { /* fall through to the queue */ }
    }
    if (outcome === "lost" && queue) {
      try { await queue(receipt); outcome = "queued"; } catch { /* nothing more to try */ }
    }
    setLast(outcome);
    return outcome;
  }, [send, queue]);
  return { record, last };
}
