import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { memberRequest, staffRequest } from "../../lib/api";
import { personalRecipientKey } from "./personalQueryKeys";
import { currentSessionContext } from "../../lib/api/sessionContext";

/**
 * Hand-typed shapes of the frozen Phase-1a notification contract
 * (`docs/notification-contract.md`, `integrations/notification_api_serializers.py`).
 * The integrator regenerates `generated/api.ts` after the merge; until then these mirror it.
 * No response ever carries a credential, a destination or a message body.
 */
export type ChannelKey = "email" | "in_app" | "telegram" | "slack" | "mattermost" | "discord" | "sms" | "whatsapp" | "native_push" | "webhook";
export type ProviderKey = "telegram" | "slack" | "mattermost" | "discord" | "twilio" | "meta" | "builtin" | "webhook";
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type WhatsAppTemplate = { feature?: string; event: string; audience: "staff" | "requester" | "member"; locale: string;
  template_name: string; variables: string[]; approved?: boolean; needs_review?: boolean };
export type Quotas = { daily_limit?: number; recipient_daily_limit?: number };
export type CallbackURLs = Partial<Record<"inbound_url" | "status_url" | "status_url_template" | "webhook_url", string>>;
export type Channel = { channel: ChannelKey; enabled: boolean; room_enabled: boolean; personal_enabled: boolean;
  provider: ProviderKey; email_fallback: boolean; integration_identity: string; generation: number;
  quotas: Quotas; credentials_set: boolean; templates: WhatsAppTemplate[];
  use_platform_sender?: boolean; sender_key?: string; credential_version?: number; activation_hold?: boolean; callback_urls?: CallbackURLs };
export type ChannelWrite = Partial<Pick<Channel, "enabled" | "room_enabled" | "personal_enabled" | "email_fallback"
  | "provider" | "integration_identity" | "quotas" | "use_platform_sender" | "activation_hold">> & { credentials?: Record<string, string>;
  templates?: Omit<WhatsAppTemplate, "approved" | "needs_review">[] };

export type Endpoint = { id: number; channel: ChannelKey; provider: ProviderKey; integration_generation: number;
  verification_state: "verified" | "revoked"; verified_at: string | null; consented_at: string | null;
  consent_version: string; revoked_at: string | null; created_at: string; effective_valid: boolean };
export type ChallengeStart = { channel: ChannelKey; consent: true; consent_version: string; phone_number?: string };
export type Challenge = { challenge_id: number; expires_at: string; connect_url?: string; instructions?: string; oauth_state?: string };
export type Selection = { category: string; channels: ChannelKey[]; email_fallback: boolean; available_channels?: ChannelKey[] };
export type Delivery = { id: number; envelope_id: number; channel: ChannelKey; state: "held" | "retrying" | "accepted" | "sent"
  | "delivered" | "read" | "failed" | "skipped"; attempt_count: number; next_attempt_at: string | null; last_error: string;
  retryable: boolean; event: string; feature: string; created_at: string; updated_at: string };
export type TestResult = { accepted: boolean; provider_id: string; retryable: boolean; error_code: string; sanitized_error: string };

/** Bumped when the consent wording shown before connecting a personal channel changes. */
export const CONSENT_VERSION = "2026-10-16";

const base = (makerspaceId: number) => `/integrations/makerspace/${makerspaceId}`;
const sender = (member: boolean) => member ? memberRequest : staffRequest;

export const channelKeys = {
  channels: (id: number) => ["notify-contract", id, "channels", currentSessionContext(), personalRecipientKey()] as const,
  personal: (id: number) => ["notify-contract", id, "personal", currentSessionContext(), personalRecipientKey()] as const,
  endpoints: (id: number) => [...channelKeys.personal(id), "endpoints"] as const,
  preferences: (id: number) => [...channelKeys.personal(id), "preferences"] as const,
  deliveries: (id: number, page: number) => [...channelKeys.personal(id), "deliveries", page] as const,
};

/** Space Manager only. Unconfigured channels have no row: the list holds configured ones. */
export function useChannels(makerspaceId: number, enabled = true) {
  return useQuery({ queryKey: channelKeys.channels(makerspaceId), enabled,
    queryFn: () => staffRequest<Page<Channel>>(`${base(makerspaceId)}/channels`) });
}

export function useSaveChannel(makerspaceId: number, channel: ChannelKey) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: ChannelWrite) => {
      const saved = await staffRequest<Channel>(`${base(makerspaceId)}/channels/${channel}`,
        { method: "PATCH", body: JSON.stringify(body) });
      if (body.credentials && (channel === "mattermost" || channel === "discord")) {
        const installed = await staffRequest<{ generation: number }>(`${base(makerspaceId)}/${channel}/installation`,
          { method: "POST", body: JSON.stringify(body.credentials) });
        return { ...saved, generation: installed.generation };
      }
      return saved;
    },
    // Enabling or rotating a channel changes what every person may choose and may revoke
    // their connections, so the personal caches refetch too.
    onSuccess: () => client.invalidateQueries({ queryKey: ["notify-contract", makerspaceId] }),
  });
}

export function useTestChannel(makerspaceId: number) {
  const client = useQueryClient();
  const personal = channelKeys.personal(makerspaceId);
  return useMutation({
    mutationFn: (body: { channel: ChannelKey; endpoint_id?: number; room_id?: number }) =>
      staffRequest<TestResult>(`${base(makerspaceId)}/channels-test`, { method: "POST", body: JSON.stringify(body) }),
    onSettled: () => client.invalidateQueries({ queryKey: personal }),
  });
}

export function useEndpoints(makerspaceId: number, member = false) {
  return useQuery({ queryKey: channelKeys.endpoints(makerspaceId),
    queryFn: async () => {
      const path = `${base(makerspaceId)}/personal/endpoints`;
      const request = sender(member);
      const first = await request<Page<Endpoint>>(path);
      const results = [...first.results];
      let next = first.next;
      while (next) {
        // DRF next links can be absolute. Keep the authenticated request on this
        // endpoint and carry forward only its pagination query.
        const page = await request<Page<Endpoint>>(`${path}${new URL(next, window.location.origin).search}`);
        results.push(...page.results);
        next = page.next;
      }
      return { ...first, next: null, results };
    } });
}

export function useOAuthReturn(makerspaceId: number, state: string | null, member = false) {
  return useQuery({ queryKey: [...channelKeys.personal(makerspaceId), "oauth-return", state], enabled: !!state, retry: false,
    queryFn: () => sender(member)<{ oauth_return: Pick<Challenge, "challenge_id" | "expires_at"> }>(
      `${base(makerspaceId)}/personal/endpoints?oauth_state=${encodeURIComponent(state ?? "")}`) });
}

export function useStartChallenge(makerspaceId: number, member = false) {
  return useMutation({
    mutationFn: (body: ChallengeStart) => sender(member)<Challenge>(`${base(makerspaceId)}/personal/endpoints/start`,
      { method: "POST", body: JSON.stringify(body) }),
  });
}

export function useVerifyChallenge(makerspaceId: number, member = false) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ challengeId, code, state }: { challengeId: number; code?: string; state?: string }) =>
      sender(member)<Endpoint>(`${base(makerspaceId)}/personal/challenges/${challengeId}/verify`,
        { method: "POST", body: JSON.stringify({ ...(code ? { code } : {}), ...(state ? { state } : {}) }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: channelKeys.personal(makerspaceId) }),
  });
}

export function useRevokeEndpoint(makerspaceId: number, member = false) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => sender(member)<{ revoked: boolean }>(`${base(makerspaceId)}/personal/endpoints/${id}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: channelKeys.personal(makerspaceId) }),
  });
}

export function usePreferences(makerspaceId: number, member = false, enabled = true) {
  return useQuery({ queryKey: channelKeys.preferences(makerspaceId), enabled, retry: false,
    queryFn: () => sender(member)<{ preferences: Selection[] }>(`${base(makerspaceId)}/personal/preferences`) });
}

export function useSavePreferences(makerspaceId: number, member = false) {
  const client = useQueryClient();
  const key = channelKeys.preferences(makerspaceId);
  return useMutation({
    // Replace supplied categories; omitted categories keep explicit choices or defaults.
    mutationFn: (preferences: Selection[]) => sender(member)<{ preferences: Selection[] }>(
      `${base(makerspaceId)}/personal/preferences`, { method: "PUT", body: JSON.stringify({
        preferences: preferences.map(({ category, channels, email_fallback }) => ({ category, channels, email_fallback })) }) }),
    onSuccess: data => {
      if (JSON.stringify(key) !== JSON.stringify(channelKeys.preferences(makerspaceId))) return;
      client.setQueryData(key, data);
      return client.invalidateQueries({ queryKey: key.slice(0, -1) });
    },
  });
}

/** The caller's own deliveries; a Space Manager sees the whole space's metadata. */
export function useDeliveries(makerspaceId: number, page: number, member = false) {
  return useQuery({ queryKey: channelKeys.deliveries(makerspaceId, page),
    queryFn: () => sender(member)<Page<Delivery>>(`${base(makerspaceId)}/personal/deliveries?page=${page}`) });
}
