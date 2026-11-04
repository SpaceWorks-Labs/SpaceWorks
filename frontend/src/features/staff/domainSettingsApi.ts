import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";

/** Mirrors `apps/makerspaces/domain_settings.py::DOMAINS`; the path decides the action checked. */
export type SettingsDomain = "events" | "bookings" | "machines" | "inventory";

export type DomainFeature = {
  key: string;
  label: string;
  description: string;
  parent_module: string | null;
  requires_features: string[];
  enabled: boolean;
  available: boolean;
  /** The caller may change it now (#101): Space Manager, a grant, or the rental-timing exception. */
  editable: boolean;
  /** A Space Manager lock blocks delegated edits of this key. */
  locked: boolean;
};

export type SettingPermission = { editable: boolean; locked: boolean };

export type DomainSettingValues = Partial<{
  event_default_registration_audience: "members" | "accounts" | "invite" | "participating_organizations";
  event_reminder_lead_hours: number[];
  booking_requester_notifications_enabled: boolean;
  booking_reminder_lead_hours: number[];
  filament_low_stock_threshold_grams: string;
}>;

export type DomainSettings = {
  domain: SettingsDomain;
  editable: boolean;
  features: DomainFeature[];
  settings: DomainSettingValues;
  setting_permissions: Record<string, SettingPermission>;
};

export type DomainSettingsPatch = { features?: Record<string, boolean>; settings?: DomainSettingValues };

export const DOMAIN_TITLES: Record<SettingsDomain, string> = {
  events: "Event settings",
  bookings: "Booking settings",
  machines: "Machine settings",
  inventory: "Lending settings",
};

export const domainSettingsKey = (makerspaceId: number, domain: SettingsDomain) =>
  ["domain-settings", makerspaceId, domain] as const;

const domainSettingsPath = (makerspaceId: number, domain: SettingsDomain) =>
  `/admin/makerspace/${makerspaceId}/domain-settings/${domain}`;

export function useDomainSettings(makerspaceId: number, domain: SettingsDomain) {
  return useQuery({
    queryKey: domainSettingsKey(makerspaceId, domain),
    queryFn: () => staffRequest<DomainSettings>(domainSettingsPath(makerspaceId, domain)),
  });
}

export function useUpdateDomainSettings(makerspaceId: number, domain: SettingsDomain) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: DomainSettingsPatch) =>
      staffRequest<DomainSettings>(domainSettingsPath(makerspaceId, domain), {
        method: "PATCH",
        body: JSON.stringify(patch),
      }),
    onSuccess: async (data) => {
      // The response is the new server state for this domain, so it replaces the cache
      // directly; the makerspace rows every console gate reads are refetched.
      client.setQueryData(domainSettingsKey(makerspaceId, domain), data);
      await Promise.all([
        ["makerspace-settings", makerspaceId], ["makerspaces"], ["staff", "makerspaces"], ["staff", "me"],
      ].map((queryKey) => client.invalidateQueries({ queryKey })));
    },
  });
}
