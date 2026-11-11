import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { memberRequest, staffRequest, StructuredApiError } from "../../../lib/api";
import { commandError, privateKey, usePrivateCommand, usePrivateQuery } from "./privateQueries";
vi.mock("../../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../../lib/api")>(), memberRequest: vi.fn(), staffRequest: vi.fn() }));
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { client, wrapper };
}
afterEach(() => vi.clearAllMocks());
describe("private event transport", () => {
  it("reuses operation/header after network failure and rotates on changed payload", async () => {
    const { wrapper } = setup();
    vi.mocked(memberRequest).mockRejectedValue(new Error("offline"));
    const { result } = renderHook(() => usePrivateCommand<{ expected_version: number; amount_minor: number }>(["test"]), { wrapper });
    const command = { path: "/member/test/", body: { expected_version: 1, amount_minor: 125000 } };
    await act(async () => { await result.current.mutateAsync(command).catch(() => undefined); });
    await act(async () => { await result.current.mutateAsync(command).catch(() => undefined); });
    const calls = vi.mocked(memberRequest).mock.calls;
    const first = calls[0][1]!;
    expect(first.cache).toBe("no-store");
    expect(calls[1][1]).toEqual(first);
    const body = JSON.parse(first.body as string);
    expect(body.operation_id).toBe((first.headers as Record<string, string>)["Idempotency-Key"]);
    await act(async () => { await result.current.mutateAsync({ ...command, body: { ...command.body, amount_minor: 1 } }).catch(() => undefined); });
    expect(vi.mocked(memberRequest).mock.calls[2][1]?.headers).not.toEqual(first.headers);
  });
  it("clears stale answers after a denied refetch", async () => {
    const { client, wrapper } = setup();
    vi.mocked(staffRequest).mockResolvedValueOnce({ answer: "private" }).mockRejectedValue(new StructuredApiError(403, {}));
    const { result } = renderHook(() => usePrivateQuery<{ answer: string }>(["private-test"], "/admin/test/", true), { wrapper });
    await waitFor(() => expect(result.current.data?.answer).toBe("private"));
    await act(async () => { await result.current.refetch(); });
    await waitFor(() => expect(result.current.data).toBeUndefined());
    await waitFor(() => expect(client.getQueryData(["private-test"])).toBeUndefined());
  });
  it("partitions actors/tenants/surfaces and hides server-provided personal error values", () => {
    const scope = { actorId: 1, makerspaceId: 2, eventId: 3 };
    expect(privateKey("stages", scope)).not.toEqual(privateKey("stages", { ...scope, actorId: 2 }));
    expect(privateKey("stages", scope)).not.toEqual(privateKey("stages", scope, true));
    expect(privateKey("stages", scope)).not.toEqual(privateKey("stages", { ...scope, makerspaceId: 4 }));
    const error = new StructuredApiError(400, { detail: "Secret account value", code: "invalid_fields" });
    expect(commandError(error)).not.toContain("Secret");
    expect(commandError(new StructuredApiError(409, { code: "stage_incomplete" }))).toMatch(/complete the required stage/i);
  });
  it("immediately clears observed data after a denied mutation", async () => {
    const { client, wrapper } = setup();
    client.setQueryData(["denied-write", "detail"], { private: "secret" });
    vi.mocked(staffRequest).mockRejectedValue(new StructuredApiError(403, {}));
    const { result } = renderHook(() => usePrivateCommand<{ expected_version: number }>(["denied-write"], true), { wrapper });
    await act(async () => { await result.current.mutateAsync({ path: "/admin/test/", body: { expected_version: 1 } }).catch(() => undefined); });
    expect(client.getQueryData(["denied-write", "detail"])).toBeUndefined();
  });
});
