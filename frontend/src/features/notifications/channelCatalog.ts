import type { Channel, ChannelKey, ProviderKey } from "./channelsApi";

export type CredentialField = { key: string; label: string; optional?: boolean; secret?: boolean; hint?: string };
export type ProviderSpec = { key: ProviderKey; label: string; identityLabel?: string; identityHint?: string;
  installation?: "slack";
  derivedIdentity?: "mattermost" | "discord";
  /** A credential the adapter reads that is the identity itself: filled from it, not typed twice. */
  identityCredential?: string;
  credentials: CredentialField[] };
export type ChannelSpec = { key: ChannelKey; label: string; description: string; rooms: boolean; personal: boolean;
  /** The module that must be installed for the channel to send (null: the notifications module alone). */
  module: string | null; providers: ProviderSpec[] };

const secret = (key: string, label: string, hint?: string): CredentialField => ({ key, label, secret: true, hint });
const plain = (key: string, label: string, hint?: string, optional = false): CredentialField => ({ key, label, hint, optional });

/**
 * What the Space Manager can set up, in the order the settings show it. Credential keys are
 * the ones the Phase-2 provider adapters read out of ChannelConfiguration's encrypted map;
 * the server validates them, this table only decides which inputs to draw.
 */
export const CHANNEL_SPECS: readonly ChannelSpec[] = [
  { key: "email", label: "Email", description: "Messages to each person's verified email address. Also the fallback when a chosen chat channel cannot deliver.",
    rooms: false, personal: true, module: "email", providers: [{ key: "builtin", label: "Space Works email", credentials: [] }] },
  { key: "telegram", label: "Telegram", description: "Group alerts for staff rooms, and private messages from your bot to people who connect their Telegram.",
    rooms: true, personal: true, module: "telegram", providers: [{ key: "telegram", label: "Telegram bot",
      identityLabel: "Bot username", identityHint: "The bot people open to connect, without the @.",
      credentials: [secret("bot_token", "Bot token", "From @BotFather.")] }] },
  { key: "slack", label: "Slack", description: "Room alerts and direct messages from your Slack app to people who sign in with Slack.",
    rooms: true, personal: true, module: "slack", providers: [{ key: "slack", label: "Slack app",
      installation: "slack", credentials: [plain("client_id", "Client ID"), secret("client_secret", "Client secret"),
        secret("signing_secret", "Signing secret")] }] },
  { key: "mattermost", label: "Mattermost", description: "Room alerts and direct messages from your Mattermost bot to people who connect their account.",
    rooms: true, personal: true, module: "mattermost", providers: [{ key: "mattermost", label: "Mattermost bot",
      derivedIdentity: "mattermost",
      credentials: [plain("server_url", "Server URL", "HTTPS origin of your Mattermost server."), secret("bot_token", "Bot token"),
        plain("client_id", "OAuth client ID"), secret("client_secret", "OAuth client secret"), secret("webhook_token", "Webhook token")] }] },
  { key: "discord", label: "Discord", description: "Room alerts and direct messages from your Discord bot to people who link their Discord account.",
    rooms: true, personal: true, module: "discord", providers: [{ key: "discord", label: "Discord bot",
      derivedIdentity: "discord", credentials: [secret("bot_token", "Bot token"), plain("application_id", "Application ID"),
        secret("client_secret", "OAuth client secret"), plain("public_key", "Public key"), plain("guild_id", "Server (guild) ID")] }] },
  { key: "whatsapp", label: "WhatsApp", description: "Personal messages to people who opt in with their WhatsApp number. Outside a 24-hour reply window only approved templates are sent.",
    rooms: false, personal: true, module: null, providers: [
      { key: "twilio", label: "Twilio", identityLabel: "WhatsApp sender number", identityHint: "E.164, for example +14155550100.",
        credentials: [plain("account_sid", "Account SID"), secret("auth_token", "Auth token"),
          plain("public_base_url", "Public callback base URL", "HTTPS origin of the API, without a path."),
          plain("api_key_sid", "API key SID", "Optional; the auth token still signs callbacks.", true),
          { ...secret("api_key_secret", "API key secret"), optional: true },
          plain("whatsapp_sender", "WhatsApp sender", "Leave empty when you use a Messaging Service.", true),
          plain("messaging_service_sid", "Messaging Service SID", undefined, true)] },
      { key: "meta", label: "Meta WhatsApp Cloud", identityLabel: "Phone number ID", identityCredential: "phone_number_id",
        credentials: [plain("app_id", "App ID"), secret("app_secret", "App secret"), plain("business_account_id", "WhatsApp Business Account ID"),
          secret("access_token", "Permanent access token"),
          secret("webhook_verify_token", "Webhook verify token")] }] },
  { key: "native_push", label: "App push", description: "Notifications on people's phones through the Space Works app. Needs the mobile push feature.",
    rooms: false, personal: true, module: null, providers: [{ key: "builtin", label: "Space Works app", credentials: [] }] },
];

export const CHANNEL_LABELS: Readonly<Record<string, string>> = {
  ...Object.fromEntries(CHANNEL_SPECS.map(spec => [spec.key, spec.label])), in_app: "Inbox", webhook: "Signed webhook",
};

/** Channels a person connects by proving an account; email, inbox and push need no connection. */
export const CONNECTABLE: readonly ChannelKey[] = ["telegram", "slack", "mattermost", "discord", "whatsapp"];

/**
 * The settings an unconfigured channel is saved with. A channel with no settings row keeps
 * today's behaviour (existing rooms post, email sends), and the first save creates the row,
 * so these defaults must reproduce that behaviour rather than switch delivery off.
 */
export function defaultChannel(spec: ChannelSpec): Channel {
  const legacyOn = spec.key === "email" || spec.key === "native_push";
  return { channel: spec.key, enabled: legacyOn || spec.rooms, room_enabled: spec.rooms, personal_enabled: legacyOn,
    provider: spec.providers[0].key, email_fallback: true, integration_identity: "", generation: 1, quotas: {},
    credentials_set: false, templates: [] };
}

export function providerSpec(spec: ChannelSpec, provider: ProviderKey) {
  return spec.providers.find(row => row.key === provider) ?? spec.providers[0];
}

export const CATEGORY_LABELS: Readonly<Record<string, string>> = {
  hardware_requests: "Hardware requests", printing: "Printing", events: "Events", bookings: "Bookings",
  maintenance: "Maintenance", members: "Members", api_access: "API access", devices: "Devices",
  payments: "Payments", stock: "Stock and procurement", certifications: "Certifications",
};
