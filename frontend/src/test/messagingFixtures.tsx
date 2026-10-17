import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { render } from "@testing-library/react";
import { vi } from "vitest";
import type { MemberMessaging, MessagingSettings, MessagingCatalogEntry, WhatsAppBinding } from "../features/messaging/messagingApi";

export const messagingSettings: MessagingSettings = {
  use_platform_sender: true, sms_account_sid: "AC" + "1".repeat(32), sms_from_number: "+14155550101",
  whatsapp_phone_number_id: "123", whatsapp_business_account_id: "456",
  sms_auth_token_set: true, whatsapp_access_token_set: true, whatsapp_app_secret_set: true,
  whatsapp_webhook_verify_token: "meta-verification-value",
  effective_source: { sms: "own", whatsapp: "platform" }, platform_available: { sms: true, whatsapp: true },
  webhook_urls: { sms: { inbound: "https://callbacks.example/api/v1/twilio/m/11/inbound#rc=5&rp=5xx,ct,rt", status: "https://callbacks.example/api/v1/twilio/m/11/status#rc=5&rp=5xx,ct,rt" },
    whatsapp: { callback: "https://callbacks.example/api/v1/whatsapp/m/11" } },
};
export const messagingCatalog: MessagingCatalogEntry[] = [
  { feature: "hardware_requests", event: "accepted", audience: "staff", allowed_projection_keys: ["makerspace_name", "request_id"], supported_languages: ["en", "hi"] },
  { feature: "hardware_requests", event: "accepted", audience: "member", allowed_projection_keys: ["request_id"], supported_languages: ["en", "hi"] },
];
export const messagingBinding: WhatsAppBinding = { id: 7, feature: "hardware_requests", event: "accepted", audience: "staff",
  business_account_id: "456", template_name: "request_accepted", language: "en", parameters: ["makerspace_name", "request_id"], is_active: false, needs_review: true };
export const memberMessaging: MemberMessaging = {
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
