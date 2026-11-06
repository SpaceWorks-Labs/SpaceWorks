import type { ProviderKey } from "./providersApi";

export type PlainField = { name: string; label: string; kind: "text" | "toggle" | "select"; hint?: string; options?: string[] };
export type SecretField = { name: string; label: string; multiline?: boolean; hint?: string };
export type ProviderSpec = { key: ProviderKey; title: string; summary: string; fields: PlainField[]; secrets: SecretField[] };

/** What each platform provider asks for. The server validates everything; this only lays out the form. */
export const PROVIDERS: ProviderSpec[] = [
  { key: "sms", title: "SMS", summary: "Sign-in codes by text (Twilio). Phone sign-in stays hidden until this is on and complete.",
    fields: [
      { name: "is_enabled", label: "Send sign-in codes by SMS", kind: "toggle" },
      { name: "provider", label: "Provider", kind: "select", options: ["twilio"] },
      { name: "account_sid", label: "Account SID", kind: "text" },
      { name: "from_number", label: "Sign-in number", kind: "text", hint: "International form, for example +447700900123." },
      { name: "notifications_enabled", label: "Also send platform notifications by SMS", kind: "toggle" },
      { name: "notifications_from_number", label: "Notifications number", kind: "text", hint: "Must differ from the sign-in number." },
    ],
    secrets: [{ name: "auth_token", label: "Auth token" }] },
  { key: "push", title: "Push", summary: "Phone notifications for the Space Works apps: Firebase (Android) and Apple Push (iOS).",
    fields: [
      { name: "apns_team_id", label: "Apple team ID", kind: "text" },
      { name: "apns_key_id", label: "Apple key ID", kind: "text" },
      { name: "apns_topic", label: "Apple topic (bundle ID)", kind: "text" },
    ],
    secrets: [
      { name: "fcm_service_account", label: "Firebase service account JSON", multiline: true },
      { name: "apns_private_key", label: "Apple push key (.p8)", multiline: true },
    ] },
  { key: "whatsapp", title: "WhatsApp", summary: "The platform's WhatsApp Business sender (Meta Cloud API).",
    fields: [
      { name: "is_enabled", label: "Use the platform WhatsApp sender", kind: "toggle" },
      { name: "app_id", label: "Meta app ID", kind: "text" },
      { name: "phone_number_id", label: "Phone number ID", kind: "text" },
      { name: "business_account_id", label: "Business account ID", kind: "text" },
    ],
    secrets: [{ name: "access_token", label: "Access token" }, { name: "app_secret", label: "App secret" }] },
  { key: "attestation", title: "App attestation", summary: "Lets the server confirm a sign-in really comes from the Space Works Android app.",
    fields: [{ name: "app_display_name", label: "App name", kind: "text" }],
    secrets: [{ name: "play_integrity_service_account", label: "Play Integrity service account JSON", multiline: true }] },
];

/** Which ways in the deployment offers. Two-step sign-in for staff is always on and is not a switch here. */
export const LOGIN_METHODS: ProviderSpec = { key: "login_methods", title: "Sign-in methods",
  summary: "Turning a method off is refused when it would leave an account with no way in.",
  fields: [
    { name: "password_enabled", label: "Password sign-in", kind: "toggle" },
    { name: "social_enabled", label: "Google, Apple and GitHub sign-in", kind: "toggle" },
    { name: "phone_enabled", label: "Phone sign-in (needs platform SMS)", kind: "toggle" },
    { name: "self_registration_enabled", label: "People may create their own account", kind: "toggle" },
    { name: "passkeys_enabled", label: "Passkeys", kind: "toggle" },
  ], secrets: [] };
