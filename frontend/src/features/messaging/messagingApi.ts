import { useQuery } from "@tanstack/react-query";
import { memberRequest, staffRequest } from "../../lib/api";

// Local contracts mirror integrations/messaging/serializers.py until client regeneration.
export type MessagingChannel = "sms" | "whatsapp";
export type MessagingSource = "own" | "platform" | "none";
export type MessagingSettings = {
  use_platform_sender: boolean;
  sms_account_sid: string;
  sms_from_number: string;
  whatsapp_phone_number_id: string;
  whatsapp_business_account_id: string;
  sms_auth_token_set: boolean;
  whatsapp_access_token_set: boolean;
  whatsapp_app_secret_set: boolean;
  whatsapp_webhook_verify_token: string;
  effective_source: Record<MessagingChannel, MessagingSource>;
  platform_available: Record<MessagingChannel, boolean>;
  webhook_urls: Record<MessagingChannel, Record<string, string>>;
};
export type MessagingSettingsWrite = Partial<Pick<MessagingSettings, "use_platform_sender" | "sms_account_sid" | "sms_from_number" | "whatsapp_phone_number_id" | "whatsapp_business_account_id"> & {
  sms_auth_token: string; whatsapp_access_token: string; whatsapp_app_secret: string;
}>;
export type MessagingCatalogEntry = {
  feature: string; event: string; audience: "member" | "staff";
  allowed_projection_keys: string[]; supported_languages: string[];
};
export type WhatsAppBindingWrite = {
  feature: string; event: string; audience: "member" | "staff";
  template_name: string; language: string; parameters: string[]; is_active: boolean;
};
export type WhatsAppBinding = WhatsAppBindingWrite & { id: number; business_account_id: string; needs_review: boolean };
export type WhatsAppBindingPage = { count: number; next: string | null; previous: string | null; results: WhatsAppBinding[] };
export type MessagingTestWrite = { channel: MessagingChannel; feature?: string; event?: string };
export type MessagingTestResult = { delivery_id: number; status: string; skip_reason: string };
export type MemberMessagingChannel = { available: boolean; consented: boolean; phone_verified: boolean; phone_masked: string; suppressed: boolean };
export type MemberMessaging = Record<MessagingChannel, MemberMessagingChannel>;
export type MessagingConsentWrite = { makerspace: number; channel: MessagingChannel; action: "opted_in" | "opted_out" };

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
export function useMemberMessaging(id: number) {
  return useQuery({ queryKey: memberMessagingKey(id), retry: false,
    queryFn: () => memberRequest<MemberMessaging>(`/me/messaging?makerspace=${id}`) });
}
