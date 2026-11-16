import { beforeEach, expect, it, vi } from "vitest";

import { enqueueReceipt, flushReceiptQueue, queuedReceiptCount } from "./receiptQueue";

const receipt = (id: string) => ({ operation_id: id, printed_at: "2026-11-11T00:00:00Z", registration_id: 1 });
beforeEach(() => { localStorage.clear(); vi.spyOn(navigator, "onLine", "get").mockReturnValue(true); });

it("keeps a receipt until it is sent, then clears it", async () => {
  await enqueueReceipt("event:1", receipt("a"));
  await enqueueReceipt("event:1", receipt("a"));
  expect(queuedReceiptCount("event:1")).toBe(1);
  const send = vi.fn().mockRejectedValueOnce(new Error("down")).mockResolvedValue({});
  expect(await flushReceiptQueue("event:1", send)).toBe(0);
  expect(queuedReceiptCount("event:1")).toBe(1);
  expect(await flushReceiptQueue("event:1", send)).toBe(1);
  expect(queuedReceiptCount("event:1")).toBe(0);
});

it("does not try to send while offline", async () => {
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  await enqueueReceipt("event:2", receipt("b"));
  const send = vi.fn();
  expect(await flushReceiptQueue("event:2", send)).toBe(0);
  expect(send).not.toHaveBeenCalled();
});
