import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { render } from "@testing-library/react";
import { vi } from "vitest";
import type { AddressedConsents } from "../features/notifications/smsConsentApi";

export const memberMessaging: AddressedConsents = {
  sms: { available: true, consented: false, phone_verified: true, phone_masked: "+1••••0101", suppressed: false },
  whatsapp: { available: true, consented: false, phone_verified: true, phone_masked: "+1••••0101", suppressed: true },
};
export function renderMessaging(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  return { ...render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>), client };
}
export function messagingFetch(responder: (url: URL, options: RequestInit) => unknown | Response | Promise<unknown | Response>) {
  const fetcher = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
    const value = await responder(new URL(String(input), "http://localhost"), options);
    return value instanceof Response ? value : new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
export const messagingFailure = (status: number, body: object) => new Response(JSON.stringify(body), { status });
