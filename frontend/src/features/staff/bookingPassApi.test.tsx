import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { bookingPassKey, useBookingPassDesigner, usePrintBookingPass } from "./bookingPassApi";

const { request, blob } = vi.hoisted(() => ({ request: vi.fn(), blob: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest: request, staffRequestBlob: blob }));

beforeEach(() => { request.mockReset(); blob.mockReset(); });
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return { client, wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> };
}

it("keys by tenant/resource, saves and invalidates layout/resource caches", async () => {
  const { client, wrapper } = setup();
  request.mockResolvedValue({ version: 2, elements: [] });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const { result } = renderHook(() => useBookingPassDesigner(3, 9), { wrapper });
  await waitFor(() => expect(result.current.query.isSuccess).toBe(true));
  expect(client.getQueryData(bookingPassKey(3, 9))).toEqual({ version: 2, elements: [] });
  expect(bookingPassKey(4, 9)).not.toEqual(bookingPassKey(3, 9));
  await act(() => result.current.save.mutateAsync({ version: 2 }));
  expect(request).toHaveBeenCalledWith("/admin/spaces/9/pass-template/", { method: "PUT", body: '{"version":2}' });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["booking-pass-template", 3, 9] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["booking-space", 9] });
});

it("staff printing sends no override and caches no rendered PDF", async () => {
  const { client, wrapper } = setup();
  const create = vi.fn(() => "blob:pass");
  const revoke = vi.fn();
  vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: revoke });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  blob.mockResolvedValue(new Blob(["private pass"], { type: "application/pdf" }));
  const { result } = renderHook(() => usePrintBookingPass(9, 12), { wrapper });
  try {
    await act(() => result.current.mutateAsync());
    expect(blob).toHaveBeenCalledWith("/admin/spaces/9/arrival/12/pass/", { method: "POST", body: "{}" });
    expect(client.getQueryCache().getAll()).toHaveLength(0);
    expect(result.current.data).toBeUndefined();
    expect(click).toHaveBeenCalledOnce();
    expect(revoke).toHaveBeenCalledWith("blob:pass");
  } finally { vi.unstubAllGlobals(); click.mockRestore(); }
});
