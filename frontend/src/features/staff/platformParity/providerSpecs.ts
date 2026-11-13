import { t } from "@lingui/core/macro";
import type { ProviderKey } from "./providersApi";

export type PlainField = { name: string; label: string; kind: "text" | "toggle" | "select"; hint?: string; options?: string[] };
export type SecretField = { name: string; label: string; multiline?: boolean; hint?: string };
export type ProviderSpec = { key: ProviderKey; title: string; summary: string; fields: PlainField[]; secrets: SecretField[] };

/** What each platform provider asks for. The server validates everything; this only lays out the form. */
export const PROVIDERS: ProviderSpec[] = [
  { key: "sms", title: "SMS", summary: t`Sign-in codes by text (Twilio). Phone sign-in stays hidden until this is on and complete.`,
    fields: [
      { name: "is_enabled", label: t`Send sign-in codes by SMS`, kind: "toggle" },
      { name: "provider", label: t`Provider`, kind: "select", options: ["twilio"] },
      { name: "account_sid", label: t`Account SID`, kind: "text" },
      { name: "from_number", label: t`Sign-in number`, kind: "text", hint: t`International form, for example +447700900123.` },
      { name: "notifications_enabled", label: t`Also send platform notifications by SMS`, kind: "toggle" },
      { name: "notifications_from_number", label: t`Notifications number`, kind: "text", hint: t`Must differ from the sign-in number.` },
    ],
    secrets: [{ name: "auth_token", label: t`Auth token` }] },
  { key: "push", title: t`Push`, summary: t`Phone notifications for the Space Works apps: Firebase (Android) and Apple Push (iOS).`,
    fields: [
      { name: "apns_team_id", label: t`Apple team ID`, kind: "text" },
      { name: "apns_key_id", label: t`Apple key ID`, kind: "text" },
      { name: "apns_topic", label: t`Apple topic (bundle ID)`, kind: "text" },
    ],
    secrets: [
      { name: "fcm_service_account", label: t`Firebase service account JSON`, multiline: true },
      { name: "apns_private_key", label: t`Apple push key (.p8)`, multiline: true },
    ] },
  { key: "whatsapp", title: t`WhatsApp`, summary: t`The platform's WhatsApp Business sender (Meta Cloud API).`,
    fields: [
      { name: "is_enabled", label: t`Use the platform WhatsApp sender`, kind: "toggle" },
      { name: "app_id", label: t`Meta app ID`, kind: "text" },
      { name: "phone_number_id", label: t`Phone number ID`, kind: "text" },
      { name: "business_account_id", label: t`Business account ID`, kind: "text" },
    ],
    secrets: [{ name: "access_token", label: t`Access token` }, { name: "app_secret", label: t`App secret` }] },
  { key: "attestation", title: t`App attestation`, summary: t`Lets the server confirm a sign-in really comes from the Space Works Android app.`,
    fields: [{ name: "app_display_name", label: t`App name`, kind: "text" }],
    secrets: [{ name: "play_integrity_service_account", label: t`Play Integrity service account JSON`, multiline: true }] },
];

/** Which ways in the deployment offers. Two-step sign-in for staff is always on and is not a switch here. */
export const LOGIN_METHODS: ProviderSpec = { key: "login_methods", title: t`Sign-in methods`,
  summary: t`Turning a method off is refused when it would leave an account with no way in.`,
  fields: [
    { name: "password_enabled", label: t`Password sign-in`, kind: "toggle" },
    { name: "social_enabled", label: t`Google, Apple and GitHub sign-in`, kind: "toggle" },
    { name: "phone_enabled", label: t`Phone sign-in (needs platform SMS)`, kind: "toggle" },
    { name: "self_registration_enabled", label: t`People may create their own account`, kind: "toggle" },
    { name: "passkeys_enabled", label: t`Passkeys`, kind: "toggle" },
  ], secrets: [] };
