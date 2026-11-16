import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";

type Page<T> = import("../publicPages/pageTypes").Collection<T>;

export type HoursPeriod = "none" | "monthly" | "yearly";
export type OrganizationHoursBank = {
  organization_id: number; makerspace_id: number; makerspace_name?: string; configured: boolean;
  allowance_minutes: number; period: HoursPeriod; period_key: string; period_ends_at: string | null;
  pool_minutes: number; used_minutes: number; remaining_minutes: number;
};
export type OrganizationHoursLedgerRow = {
  id: number; entry: "grant" | "consume" | "release" | "adjust"; minutes: number; period_key: string;
  booking_id: number | null; reason: string; actor_name?: string; created_at: string;
};

/** Open item B13: query keys for an organization's hours bank (staff view per space, org-admin view per org). */
export const organizationHoursKeys = {
  all: ["organization-hours"] as const,
  bank: (makerspaceId: number, organizationId: number) => ["organization-hours", "bank", makerspaceId, organizationId] as const,
  ledger: (makerspaceId: number, organizationId: number, page: number) =>
    ["organization-hours", "ledger", makerspaceId, organizationId, page] as const,
  own: (organizationId: number) => ["organization-hours", "own", organizationId] as const,
  ownLedger: (organizationId: number, makerspaceId: number, page: number) =>
    ["organization-hours", "own-ledger", organizationId, makerspaceId, page] as const,
};

const staffBase = (makerspaceId: number, organizationId: number) =>
  `/admin/makerspace/${makerspaceId}/organizations/${organizationId}/hours-bank/`;

export function useOrganizationHoursBank(makerspaceId: number, organizationId: number) {
  return useQuery({ queryKey: organizationHoursKeys.bank(makerspaceId, organizationId), retry: false,
    queryFn: () => staffRequest<OrganizationHoursBank>(staffBase(makerspaceId, organizationId)) });
}

export function useOrganizationHoursLedger(makerspaceId: number, organizationId: number, page: number) {
  return useQuery({ queryKey: organizationHoursKeys.ledger(makerspaceId, organizationId, page), retry: false,
    placeholderData: keepPreviousData,
    queryFn: () => staffRequest<Page<OrganizationHoursLedgerRow>>(`${staffBase(makerspaceId, organizationId)}ledger/?page=${page}`) });
}

/** Every write changes the balance and appends a ledger row, so both caches are refreshed together. */
export function useOrganizationHoursWrites(makerspaceId: number, organizationId: number) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: organizationHoursKeys.all });
  const saveAllowance = useMutation({
    mutationFn: (body: { allowance_minutes: number; period: HoursPeriod }) =>
      staffRequest<OrganizationHoursBank>(staffBase(makerspaceId, organizationId), { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: refresh });
  const adjust = useMutation({
    mutationFn: (body: { entry: "grant" | "adjust"; minutes: number; reason: string }) =>
      staffRequest<OrganizationHoursLedgerRow>(`${staffBase(makerspaceId, organizationId)}ledger/`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: refresh });
  return { saveAllowance, adjust };
}

export function useOwnOrganizationHours(organizationId: number, enabled: boolean) {
  return useQuery({ queryKey: organizationHoursKeys.own(organizationId), enabled, retry: false,
    queryFn: () => staffRequest<{ banks: OrganizationHoursBank[] }>(`/admin/organizations/${organizationId}/hours-bank/`) });
}

export function useOwnOrganizationHoursLedger(organizationId: number, makerspaceId: number, page: number, enabled: boolean) {
  return useQuery({ queryKey: organizationHoursKeys.ownLedger(organizationId, makerspaceId, page), enabled, retry: false,
    placeholderData: keepPreviousData,
    queryFn: () => staffRequest<Page<OrganizationHoursLedgerRow>>(
      `/admin/organizations/${organizationId}/hours-bank/${makerspaceId}/ledger/?page=${page}`) });
}
