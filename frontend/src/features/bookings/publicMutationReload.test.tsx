import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, QueryObserver } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { EventRegistrationForm } from "../inventory/EventRegistrationForm";
import { useSubmitPublicBooking } from "./publicBookingsApi";
import { cacheTenantPublishableKey, clearAccessToken, getAccessToken, setAccessToken } from "../../lib/api/client";
import { publicV1Request } from "../../lib/api/requests";
import { setRouteSessionContext } from "../../lib/api/sessionContext";
import { queryClientForContext } from "../../lib/queryClient";

vi.mock("../../features/staff/eventCheckInOfflineStore", () => ({ wipeOfflineScopes: vi.fn(async () => undefined) }));
vi.mock("../../lib/charges", () => ({ useChargesOn: () => false }));
vi.mock("../payments/PricePreview", () => ({ PricePreview: () => null }));
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const person = `e30.${btoa(JSON.stringify({ user_id: 7 }))}.signature`;
const platform = `e30.${btoa(JSON.stringify({ user_id: 9 }))}.signature`;
const input = { starts_at: "2026-11-09T10:00:00Z", ends_at: "2026-11-09T11:00:00Z" };
function wrapper({ children }: PropsWithChildren) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
}
beforeEach(() => {
  setRouteSessionContext("person"); clearAccessToken("person"); clearAccessToken("platform");
  cacheTenantPublishableKey("lab", "lab-explicit-key");
  cacheTenantPublishableKey("other", "other-ambient-key");
});
afterEach(() => { clearAccessToken("person"); clearAccessToken("platform"); setRouteSessionContext("person"); vi.unstubAllGlobals(); });

it.each(["booking", "registration"])("restores cookie auth for the actual %s mutation without borrowing platform authority", async kind => {
  setRouteSessionContext("platform"); setAccessToken(platform, "platform");
  let attempts = 0;
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/auth/refresh")) {
      expect(JSON.parse(options?.body as string)).toEqual({ context: "person" });
      expect(options?.credentials).toBe("include");
      return json({ access: person });
    }
    attempts++;
    const headers = new Headers(options?.headers);
    expect(headers.get("X-Publishable-Key")).toBe("lab-explicit-key");
    expect(headers.get("Authorization")).toBe(attempts === 1 ? null : `Bearer ${person}`);
    expect(options?.method).toBe("POST");
    return attempts === 1 ? json({ detail: "Not authenticated." }, 401)
      : json({ status: kind === "booking" ? "pending" : "registered" }, 201);
  });
  vi.stubGlobal("fetch", fetcher);
  if (kind === "booking") {
    const { result } = renderHook(() => useSubmitPublicBooking("lab", "resource"), { wrapper });
    await act(async () => { expect(await result.current.mutateAsync(input)).toEqual({ status: "pending" }); });
  } else {
    render(<EventRegistrationForm makerspaceSlug="lab" publicToken="event" waitlist={false}
      approvalRequired={false} customForm={[]} />, { wrapper });
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    await waitFor(() => expect(screen.getByText("Registration received")).toBeVisible());
  }
  expect(attempts).toBe(2);
  expect(fetcher).toHaveBeenCalledTimes(3);
  expect(getAccessToken("platform")).toBe(platform);
});

it("refuses an anonymous booking without clearing another active query or replaying it anonymously", async () => {
  const client = queryClientForContext("person");
  const observer = new QueryObserver(client, { queryKey: ["public", "unrelated"], queryFn: async () => "retained" });
  const unsubscribe = observer.subscribe(() => {});
  try {
    await vi.waitFor(() => expect(observer.getCurrentResult().status).toBe("success"));
    const fetcher = vi.fn(async () => json({ detail: "Not authenticated." }, 401));
    vi.stubGlobal("fetch", fetcher);
    const { result } = renderHook(() => useSubmitPublicBooking("lab", "resource"), { wrapper });
    await act(async () => { await expect(result.current.mutateAsync(input)).rejects.toMatchObject({ status: 401 }); });
    expect(fetcher).toHaveBeenCalledTimes(2); // one refused mutation, one refused person refresh
    expect(observer.getCurrentResult()).toMatchObject({ status: "success", data: "retained" });
    expect(client.getQueryCache().find({ queryKey: ["public", "unrelated"] })).toBeDefined();
  } finally { unsubscribe(); }
});

it.each(["/auth/login", "/auth/password-reset", "/public/anonymous-submission"])("leaves generic public mutation %s without an authentication replay", async path => {
  setRouteSessionContext("platform"); setAccessToken(platform, "platform");
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) => {
    expect(new Headers(options?.headers).get("Authorization")).toBeNull();
    return json({ detail: "Refused." }, 401);
  });
  vi.stubGlobal("fetch", fetcher);
  await expect(publicV1Request(path, { method: "POST", body: "{}" })).rejects.toMatchObject({ status: 401 });
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(getAccessToken("platform")).toBe(platform);
});
