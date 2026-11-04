import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiPath } from "../../generated/api";
import { staffRequest } from "../../lib/api";
import { eventKeys, staffPath, type Paginated, type StaffEvent } from "./eventsApiTypes";
import { organizedEventKeys } from "./organizedEventsApi";

export type DirectoryOrganization = { id: number; name: string; slug: string; logo_url: string | null };
export type DirectoryMakerspace = { id: number; name: string; slug: string };
export type EventCheckInRow = {
  registration_id: number; attendee_name: string; ticket_type: string | null;
  attended_at: string | null; source: "qr" | "manual" | "offline" | "station" | "legacy";
  checked_in_by: string | null;
};

const ORGANIZATION_DIRECTORY_PATH: ApiPath = "/api/v1/admin/organizations/directory/";
const PARTNER_DIRECTORY_PATH: ApiPath = "/api/v1/admin/event-partner-makerspaces/";
const AUDIENCE_PATH: ApiPath = "/api/v1/admin/events/{id}/audience-organizations/";
const CHECK_INS_PATH: ApiPath = "/api/v1/admin/events/{id}/check-ins/";

export const directoryKeys = {
  organizations: (search: string) => ["directory", "organizations", search] as const,
  makerspaces: (search: string, exclude?: number) => ["directory", "event-partners", search, exclude ?? null] as const,
};

function query(params: Record<string, string | number | undefined>) {
  const values = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== "") values.set(key, String(value)); });
  return values.toString();
}

/** Discoverable organizations plus the actor's own; the audience picker's source. */
export function useOrganizationDirectory(search: string, enabled = true) {
  return useQuery({ queryKey: directoryKeys.organizations(search), enabled, placeholderData: keepPreviousData,
    queryFn: () => staffRequest<Paginated<DirectoryOrganization>>(`${staffPath(ORGANIZATION_DIRECTORY_PATH, {})}?${query({ search })}`) });
}

/** The central public directory plus spaces the actor manages, minus the host. */
export function usePartnerMakerspaces(search: string, exclude?: number, enabled = true) {
  return useQuery({ queryKey: directoryKeys.makerspaces(search, exclude), enabled, placeholderData: keepPreviousData,
    queryFn: () => staffRequest<Paginated<DirectoryMakerspace>>(`${staffPath(PARTNER_DIRECTORY_PATH, {})}?${query({ search, exclude })}`) });
}

export function useReplaceAudienceOrganizations(makerspaceId: number, eventId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (organizationIds: number[]) => staffRequest<{ audience_organizations: StaffEvent["audience_organizations"] }>(
      staffPath(AUDIENCE_PATH, { id: eventId }),
      { method: "PUT", body: JSON.stringify({ organization_ids: organizationIds }) },
    ),
    // Eligibility, the roster's "no longer eligible" flags and public attribution all move.
    onSuccess: async () => { await Promise.all([
      client.invalidateQueries({ queryKey: eventKeys.detail(eventId) }),
      client.invalidateQueries({ queryKey: eventKeys.registrations(eventId) }),
      client.invalidateQueries({ queryKey: ["event", eventId, "eligible-members"] }),
      client.invalidateQueries({ queryKey: ["event-organization-eligibility"] }),
      client.invalidateQueries({ queryKey: ["public-events"] }),
      client.invalidateQueries({ queryKey: ["public-event"] }),
      client.invalidateQueries({ queryKey: eventKeys.list(makerspaceId) }),
      client.invalidateQueries({ queryKey: organizedEventKeys.all }),
    ]); },
  });
}

/** Who has checked in. Scans invalidate `checkinHistory`; the interval covers other doors. */
export function useEventCheckIns(eventId: number, page = 1, enabled = true) {
  return useQuery({ queryKey: [...eventKeys.checkinHistory(eventId), page], enabled, refetchInterval: 15_000,
    placeholderData: keepPreviousData,
    queryFn: () => staffRequest<Paginated<EventCheckInRow>>(`${staffPath(CHECK_INS_PATH, { id: eventId })}?page=${page}`) });
}
