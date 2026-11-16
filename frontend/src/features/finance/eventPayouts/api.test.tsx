import { describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { staffRequest } from "../../../lib/api";
import { commandPath, payoutKey, usePayoutCommand, usePayouts } from "./api";
import { scope } from "./testData";
import { money, utcInstant } from "./format";
vi.mock("../../../lib/api", () => ({ staffRequest: vi.fn(), memberRequest: vi.fn() }));
function wrapper({ children }: PropsWithChildren) { return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>; }
describe("payout wire contracts", () => {
  it("uses the frozen root entry route", () => {
    expect(commandPath(scope, "obligation", "entries/entry/amend")).toBe("/admin/makerspaces/2/event-payouts/entries/entry/amend/");
    expect(commandPath(scope, "obligation", "cancel")).toBe("/admin/makerspaces/2/event-payouts/obligation/cancel/");
  });
  it("partitions caches by host, actor and makerspace and passes cancellation", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ count: 0, results: [], next: null, previous: null });
    expect(payoutKey(scope)).not.toEqual(payoutKey({ ...scope, actorId: 9 }));
    expect(payoutKey(scope)).not.toEqual(payoutKey({ ...scope, makerspaceId: 9 }));
    const hook = renderHook(() => usePayouts(scope, 2), { wrapper });
    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));
    expect(staffRequest).toHaveBeenLastCalledWith("/admin/makerspaces/2/event-payouts/?page=2", expect.objectContaining({ cache: "no-store", signal: expect.any(AbortSignal) }));
  });
  it("retries an uncertain command with the same UUID and changes it for altered payload", async () => {
    vi.mocked(staffRequest).mockRejectedValue(new Error("uncertain response"));
    const hook = renderHook(() => usePayoutCommand(scope, "obligation", "acknowledge-eligibility"), { wrapper });
    const data = { expected_version: 3, eligibility_revision: 2, reason_code: "evidence_reviewed" };
    await act(async () => { await hook.result.current.mutateAsync(data).catch(() => {}); });
    const first = JSON.parse(vi.mocked(staffRequest).mock.calls.at(-1)![1]!.body as string);
    await act(async () => { await hook.result.current.mutateAsync(data).catch(() => {}); });
    const second = JSON.parse(vi.mocked(staffRequest).mock.calls.at(-1)![1]!.body as string);
    expect(second.operation_id).toBe(first.operation_id);
    await act(async () => { await hook.result.current.mutateAsync({ ...data, expected_version: 4 }).catch(() => {}); });
    const last = vi.mocked(staffRequest).mock.calls.at(-1)![1]!;
    expect(JSON.parse(last.body as string).operation_id).not.toBe(first.operation_id);
    expect(JSON.parse(last.body as string).operation_id).toBe((last.headers as Record<string, string>)["Idempotency-Key"]);
  });
  it("normalizes UTC seconds and supports actual currency exponents", () => {
    expect(utcInstant("2026-12-01T10:00")).toBe("2026-12-01T10:00:00Z");
    expect(utcInstant("2026-12-01T10:00:32.123")).toBe("2026-12-01T10:00:32.123Z");
    expect(utcInstant("2026-02-30T10:00")).toBeNull();
    expect(utcInstant("garbage")).toBeNull();
    expect(money(1000, "JPY")).toMatch(/1,000/);
    expect(money(1000, "KWD")).toMatch(/1\.000/);
    expect(money(null, "INR")).toBe("Unavailable");
    expect(money(8_999_999_999_999_999, "USD").replace(/,/g, "")).toContain("89999999999999.99");
  });
});
