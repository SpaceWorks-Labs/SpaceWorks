import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest, staffRequest } from "../../lib/api";
import { channelKeys } from "./channelsApi";

export type AddressedConsent = { available: boolean; consented: boolean; phone_verified: boolean;
  phone_masked: string; suppressed: boolean };
export type AddressedConsents = { sms: AddressedConsent; whatsapp: AddressedConsent };
export const smsConsentKey = (id: number) => [...channelKeys.personal(id), "sms-consent"] as const;

// This retained core API records sender/phone-instance consent. It does not configure
// delivery or prove WhatsApp ownership; those belong to the canonical channel APIs.
export function useSmsConsent(id: number, enabled = true, member = true) {
  return useQuery({ queryKey: smsConsentKey(id), retry: false, enabled,
    queryFn: () => (member ? memberRequest : staffRequest)<AddressedConsents>(`/me/messaging?makerspace=${id}`) });
}

export function useSaveSmsConsent(id: number, member = true) {
  const client = useQueryClient();
  const key = smsConsentKey(id);
  const personal = channelKeys.personal(id);
  return useMutation({ mutationFn: (allowed: boolean) => (member ? memberRequest : staffRequest)<AddressedConsents>("/me/messaging/consent", {
    method: "POST", body: JSON.stringify({ makerspace: id, channel: "sms", action: allowed ? "opted_in" : "opted_out" }),
  }), onSuccess: data => {
    // A completion from an old account must never populate the next account's cache.
    if (JSON.stringify(key) !== JSON.stringify(smsConsentKey(id))) return;
    client.setQueryData(key, data);
    return client.invalidateQueries({ queryKey: personal });
  } });
}
