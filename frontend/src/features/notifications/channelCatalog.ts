import { t } from "@lingui/core/macro";
import type { Channel, ChannelKey, ProviderKey } from "./channelsApi";

export type CredentialField = { key: string; label: string; optional?: boolean; secret?: boolean; hint?: string };
export type ProviderSpec = { key: ProviderKey; label: string; identityLabel?: string; identityHint?: string;
  installation?: "slack";
  derivedIdentity?: "mattermost" | "discord";
  /** A credential the adapter reads that is the identity itself: filled from it, not typed twice. */
  identityCredential?: string;
  credentials: CredentialField[] };
export type ChannelSpec = { key: ChannelKey; label: string; description: string; rooms: boolean; personal: boolean;
  /** The channel's module; null means core or feature policy, independent of the optional inbox. */
  module: string | null; providers: ProviderSpec[] };

const secret = (key: string, label: string, hint?: string): CredentialField => ({ key, label, secret: true, hint });
const plain = (key: string, label: string, hint?: string, optional = false): CredentialField => ({ key, label, hint, optional });

/**
 * What the Space Manager can set up, in the order the settings show it. Credential keys are
 * the ones the Phase-2 provider adapters read out of ChannelConfiguration's encrypted map;
 * the server validates them, this table only decides which inputs to draw.
 */
export function channelSpecs(): readonly ChannelSpec[] {
  return [
    { key: "email", label: t`Email`, description: t`Messages to each person's verified email address. Also the fallback when a chosen chat channel cannot deliver.`,
      rooms: false, personal: true, module: "email", providers: [{ key: "builtin", label: t`Space Works email`, credentials: [] }] },
    { key: "telegram", label: t`Telegram`, description: t`Group alerts for staff rooms, and private messages from your bot to people who connect their Telegram.`,
      rooms: true, personal: true, module: "telegram", providers: [{ key: "telegram", label: t`Telegram bot`,
        identityLabel: t`Bot username`, identityHint: t`The bot people open to connect, without the @.`,
        credentials: [secret("bot_token", t`Bot token`, t`From @BotFather.`)] }] },
    { key: "slack", label: t`Slack`, description: t`Room alerts and direct messages from your Slack app to people who sign in with Slack.`,
      rooms: true, personal: true, module: "slack", providers: [{ key: "slack", label: t`Slack app`,
        installation: "slack", credentials: [plain("client_id", t`Client ID`), secret("client_secret", t`Client secret`),
          secret("signing_secret", t`Signing secret`)] }] },
    { key: "mattermost", label: t`Mattermost`, description: t`Room alerts and direct messages from your Mattermost bot to people who connect their account.`,
      rooms: true, personal: true, module: "mattermost", providers: [{ key: "mattermost", label: t`Mattermost bot`,
        derivedIdentity: "mattermost",
        credentials: [plain("server_url", t`Server URL`, t`HTTPS origin of your Mattermost server.`), secret("bot_token", t`Bot token`),
          plain("client_id", t`OAuth client ID`), secret("client_secret", t`OAuth client secret`), secret("webhook_token", t`Webhook token`)] }] },
    { key: "discord", label: t`Discord`, description: t`Room alerts and direct messages from your Discord bot to people who link their Discord account.`,
      rooms: true, personal: true, module: "discord", providers: [{ key: "discord", label: t`Discord bot`,
        derivedIdentity: "discord", credentials: [secret("bot_token", t`Bot token`), plain("application_id", t`Application ID`),
          secret("client_secret", t`OAuth client secret`), plain("public_key", t`Public key`), plain("guild_id", t`Server (guild) ID`)] }] },
    { key: "sms", label: t`SMS`, description: t`Personal texts to verified phone numbers with separate consent for this space and sender.`,
      rooms: false, personal: true, module: "sms", providers: [{ key: "twilio", label: t`Twilio`,
        credentials: [plain("account_sid", t`Account SID`), secret("auth_token", t`Auth token`), plain("from_number", t`Sender phone number`, t`E.164, for example +14155550100.`)] }] },
    { key: "whatsapp", label: t`WhatsApp`, description: t`Personal messages to people who connect their WhatsApp account. Outside a 24-hour reply window only approved templates are sent.`,
      rooms: false, personal: true, module: "whatsapp", providers: [
        { key: "twilio", label: t`Twilio`, identityLabel: t`WhatsApp sender number`, identityHint: t`E.164, for example +14155550100.`,
          credentials: [plain("account_sid", t`Account SID`), secret("auth_token", t`Auth token`),
            plain("public_base_url", t`Public callback base URL`, t`HTTPS origin of the API, without a path.`),
            plain("api_key_sid", t`API key SID`, t`Optional; the auth token still signs callbacks.`, true),
            { ...secret("api_key_secret", t`API key secret`), optional: true },
            plain("whatsapp_sender", t`WhatsApp sender`, t`Leave empty when you use a Messaging Service.`, true),
            plain("messaging_service_sid", t`Messaging Service SID`, undefined, true)] },
        { key: "meta", label: t`Meta WhatsApp Cloud`, identityLabel: t`Phone number ID`, identityCredential: "phone_number_id",
          credentials: [plain("app_id", t`App ID`), secret("app_secret", t`App secret`), plain("business_account_id", t`WhatsApp Business Account ID`),
            secret("access_token", t`Permanent access token`),
            secret("webhook_verify_token", t`Webhook verify token`)] }] },
    { key: "native_push", label: t`App push`, description: t`Notifications on people's phones through the Space Works app. Needs the mobile push feature.`,
      rooms: false, personal: true, module: "mobile", providers: [{ key: "builtin", label: t`Space Works app`, credentials: [] }] },
  ];
}

/** A channel key as people read it, in the active language; the raw key only for an unknown one. */
export function channelLabel(key: string): string {
  const labels: Record<string, string> = {
    ...Object.fromEntries(channelSpecs().map(spec => [spec.key, spec.label])), in_app: t`Inbox`, webhook: t`Signed webhook`,
  };
  return labels[key] ?? key.replace(/_/g, " ");
}

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
    credentials_set: false, templates: [], use_platform_sender: false, activation_hold: false };
}

export function providerSpec(spec: ChannelSpec, provider: ProviderKey) {
  return spec.providers.find(row => row.key === provider) ?? spec.providers[0];
}

/** A notification category as people read it; the raw key only for an unknown one. */
export function categoryLabel(key: string): string {
  const labels: Record<string, string> = {
    hardware_requests: t`Hardware requests`, printing: t`Printing`, events: t`Events`, bookings: t`Bookings`,
    maintenance: t`Maintenance`, members: t`Members`, api_access: t`API access`, devices: t`Devices`,
    payments: t`Payments`, stock: t`Stock and procurement`, certifications: t`Certifications`, presence: t`Presence`,
  };
  return labels[key] ?? key.replace(/_/g, " ");
}
