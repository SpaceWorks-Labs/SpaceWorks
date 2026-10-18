import { useQuery } from "@tanstack/react-query";
import { memberRequest, staffRequest } from "../../lib/api";

import type { MemberMessaging, MessagingSettings, MessagingTest, WhatsAppBinding as GeneratedWhatsAppBinding,
  WhatsAppBindingPage as GeneratedWhatsAppBindingPage, PatchedMessagingSettings, ConsentWrite } from "../../generated/api";
export type { MemberMessaging, MessagingSettings, MessagingCatalogEntry,
  MessagingChannel as MemberMessagingChannel, MessagingTestResponse as MessagingTestResult } from "../../generated/api";
export type MessagingChannel = MessagingTest["channel"];
export type MessagingSource = MessagingSettings["effective_source"][string];
export type MessagingTestWrite = MessagingTest;
export type MessagingSettingsWrite = Pick<PatchedMessagingSettings,
  "use_platform_sender" | "sms_account_sid" | "sms_from_number" | "whatsapp_phone_number_id" |
  "whatsapp_business_account_id" | "sms_auth_token" | "whatsapp_access_token" | "whatsapp_app_secret">;
// OpenAPI leaves parameters as unknown JSON; the binding editor handles ordered BODY variable names.
export type WhatsAppBinding = Omit<GeneratedWhatsAppBinding, "parameters"> & { parameters: string[] };
export type WhatsAppBindingWrite = Pick<WhatsAppBinding,
  "feature" | "event" | "audience" | "template_name" | "language" | "parameters" | "is_active">;
export type WhatsAppBindingPage = Omit<GeneratedWhatsAppBindingPage, "results"> & { results: WhatsAppBinding[] };
export type MessagingConsentWrite = ConsentWrite;

export const messagingLabels = { sms: "SMS", whatsapp: "WhatsApp" };
export const messagingSettingsKey = (id: number) => ["messaging-settings", id] as const;
export const memberMessagingKey = (id: number) => ["member", "messaging", id] as const;
export const templateBindingsKey = (id: number) => ["whatsapp-templates", id] as const;
export const messagingSettingsPath = (id: number) => `/admin/makerspace/${id}/messaging-settings`;
export const templateBindingsPath = (id: number) => `/admin/makerspace/${id}/whatsapp-templates`;
export function useMessagingSettings(id: number, enabled = true) {
  return useQuery({ queryKey: messagingSettingsKey(id), enabled,
    queryFn: () => staffRequest<MessagingSettings>(messagingSettingsPath(id)) });
}
export function useMemberMessaging(id: number, enabled = true) {
  return useQuery({ queryKey: memberMessagingKey(id), enabled, retry: false,
    queryFn: () => memberRequest<MemberMessaging>(`/me/messaging?makerspace=${id}`) });
}
