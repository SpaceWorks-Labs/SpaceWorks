import type { ReactNode } from "react";
import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { useCloneBookingSpace, useEditBooking } from "./bookingToolsApi";
import { useBookingAction } from "./bookingsApi";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request }));
beforeEach(() => { request.mockReset().mockResolvedValue({ id: 8 }); });
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries").mockResolvedValue();
  return { invalidate, wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> };
}
it("uses strict edit routes and invalidates every affected server projection", async () => {
  const { wrapper, invalidate } = setup();
  const { result } = renderHook(() => useEditBooking(3, 8, 2), { wrapper });
  await act(async () => { await result.current.mutateAsync({ kind: "details", note: "Note", custom_answers: { purpose: "Robot" } }); });
  expect(request).toHaveBeenLastCalledWith("/admin/bookings/2/details/", { method: "PATCH", body: JSON.stringify({ note: "Note", custom_answers: { purpose: "Robot" } }) });
  expect(invalidate.mock.calls.map(([value]) => value?.queryKey)).toEqual(expect.arrayContaining([
    ["booking-space", 8, "bookings"], ["booking-space", 8, "availability"], ["bookings", 3, "spaces"], ["public-space-availability"], ["operations-report"], ["member"], ["bookings", "accessible"],
  ]));
  await act(async () => { await result.current.mutateAsync({ kind: "time", starts_at: "2099-01-01T12:00:00Z", ends_at: "2099-01-01T13:00:00Z" }); });
  expect(request).toHaveBeenLastCalledWith("/admin/bookings/2/time/", expect.objectContaining({ method: "POST" }));
});
it("posts clone rules explicitly and refreshes resource discovery", async () => {
  const { wrapper, invalidate } = setup();
  const { result } = renderHook(() => useCloneBookingSpace(3, 8), { wrapper });
  await act(async () => { await result.current.mutateAsync(false); });
  expect(request).toHaveBeenCalledWith("/admin/spaces/8/clone/", { method: "POST", body: '{"copy_booking_rules":false}' });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["bookings", 3, "spaces"] });
});
it("sends only edited detail fields in the PATCH body", async () => {
  const { wrapper } = setup();
  const { result } = renderHook(() => useEditBooking(3, 8, 2), { wrapper });
  await act(async () => { await result.current.mutateAsync({ kind: "details", note: "Note only" }); });
  expect(request).toHaveBeenLastCalledWith("/admin/bookings/2/details/", { method: "PATCH", body: '{"note":"Note only"}' });
  await act(async () => { await result.current.mutateAsync({ kind: "details", custom_answers: { purpose: "Robot" } }); });
  expect(request).toHaveBeenLastCalledWith("/admin/bookings/2/details/", { method: "PATCH", body: '{"custom_answers":{"purpose":"Robot"}}' });
});
it("undo uses the named action endpoint and failures do not invalidate", async () => {
  const { wrapper, invalidate } = setup();
  const { result } = renderHook(() => useBookingAction(3, 8), { wrapper });
  request.mockRejectedValueOnce(new Error("window_expired"));
  await act(async () => { await expect(result.current.mutateAsync({ bookingId: 2, action: "restore" })).rejects.toThrow("window_expired"); });
  expect(invalidate).not.toHaveBeenCalled();
  expect(request).toHaveBeenCalledWith("/admin/bookings/2/restore/", { method: "POST", body: "{}" });
});
