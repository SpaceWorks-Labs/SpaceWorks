import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { Paginated } from "../eventsApiTypes";
import type { RefundPolicySummary, TicketOrder } from "../../events/ticketing/ticketingApi";

/** Release 2 L6 staff surfaces: orders, add-ons, sales rules, refund override, venue fee, passes, desk. */

export type StaffAddon = { id: number; name: string; description: string; kind: string; amount: string; stock: number;
  per_order_limit: number; is_active: boolean; remaining: number | null; sold: number;
  variants: { id?: number; label: string; stock: number; is_active?: boolean; remaining?: number | null }[] };
export type SalesSettings = { booking_fee_fixed: string; booking_fee_bps: number; max_tickets_per_order: number;
  transfers_allowed: boolean; type_changes_allowed: boolean; transfer_cutoff_hours: number };
export type StaffRefundPolicy = RefundPolicySummary & { locked: boolean };
export type RefundPolicyInput = { enabled: boolean; full_before_minutes: number; partial_before_minutes: number;
  partial_percent: number; cancellation_fee: string; policy_text: string };
export type VenueFee = { id: number; payer: number; payer_name: string; organization: number | null; room: number | null;
  mode: "inherit" | "free" | "custom"; basis: "flat" | "per_hour"; amount: string | null;
  status: "configured" | "charged" | "free"; charged_at: string | null; quote_total: string; payment_id: number | null };
export type VenueFeeInput = { payer_id: number; organization_id?: number | null; room_id?: number | null;
  mode: VenueFee["mode"]; basis: VenueFee["basis"]; amount?: string | null };
export type StaffOrder = TicketOrder & { buyer: number; buyer_name: string };
export type PassType = { id?: number; name: string; amount: string; capacity: number; occurrence_refund_amount: string;
  sales_end_at: string | null; is_active: boolean; sold?: number };

const send = (method: string, body: unknown = {}): RequestInit => ({ method, body: JSON.stringify(body) });
const eventPath = (eventId: number, rest: string) => `/admin/events/${eventId}/${rest}/`;

function useRefresh(keys: unknown[][]) {
  const client = useQueryClient();
  return () => Promise.all(keys.map(queryKey => client.invalidateQueries({ queryKey })));
}

export function useEventAddons(eventId: number) {
  const key = ["event", eventId, "addons"];
  const refresh = useRefresh([key, ["event-ticket-shop"]]);
  const rows = useQuery({ queryKey: key, queryFn: () => staffRequest<Paginated<StaffAddon>>(eventPath(eventId, "addons")) });
  const create = useMutation({ onSuccess: refresh, mutationFn: (body: Partial<StaffAddon>) =>
    staffRequest<StaffAddon>(eventPath(eventId, "addons"), send("POST", body)) });
  const update = useMutation({ onSuccess: refresh, mutationFn: ({ id, patch }: { id: number; patch: Partial<StaffAddon> }) =>
    staffRequest<StaffAddon>(`/admin/event-addons/${id}/`, send("PATCH", patch)) });
  const remove = useMutation({ onSuccess: refresh, mutationFn: (id: number) =>
    staffRequest<void>(`/admin/event-addons/${id}/`, { method: "DELETE" }) });
  return { rows, create, update, remove };
}

export function useSalesSettings(eventId: number) {
  const key = ["event", eventId, "sales-settings"];
  const refresh = useRefresh([key]);
  const settings = useQuery({ queryKey: key, queryFn: () => staffRequest<SalesSettings>(eventPath(eventId, "sales-settings")) });
  const save = useMutation({ onSuccess: refresh, mutationFn: (body: SalesSettings) =>
    staffRequest<SalesSettings>(eventPath(eventId, "sales-settings"), send("PUT", body)) });
  return { settings, save };
}

export function useEventOrders(eventId: number, page = 1) {
  return useQuery({ queryKey: ["event", eventId, "orders", page],
    queryFn: () => staffRequest<Paginated<StaffOrder>>(`${eventPath(eventId, "orders")}?page=${page}`) });
}

export function useRefundPolicy(eventId: number) {
  const key = ["event", eventId, "refund-policy"];
  const refresh = useRefresh([key, ["event-ticket-shop"]]);
  const policy = useQuery({ queryKey: key, queryFn: () => staffRequest<StaffRefundPolicy>(eventPath(eventId, "refund-policy")) });
  const save = useMutation({ onSuccess: refresh, mutationFn: (body: RefundPolicyInput) =>
    staffRequest<StaffRefundPolicy>(eventPath(eventId, "refund-policy"), send("POST", body)) });
  return { policy, save };
}

export function useVenueFee(eventId: number) {
  const key = ["event", eventId, "venue-fee"];
  const refresh = useRefresh([key]);
  const fee = useQuery({ queryKey: key, retry: false,
    queryFn: () => staffRequest<VenueFee>(eventPath(eventId, "venue-fee")) });
  const save = useMutation({ onSuccess: refresh, mutationFn: (body: VenueFeeInput) =>
    staffRequest<VenueFee>(eventPath(eventId, "venue-fee"), send("PUT", body)) });
  const charge = useMutation({ onSuccess: refresh, mutationFn: () =>
    staffRequest<VenueFee>(`/admin/events/${eventId}/venue-fee/charge/`, send("POST")) });
  return { fee, save, charge };
}

export function usePassTypes(seriesId: number) {
  const key = ["event-series", seriesId, "pass-types"];
  const refresh = useRefresh([key]);
  const rows = useQuery({ queryKey: key, queryFn: () => staffRequest<Paginated<PassType>>(`/admin/event-series/${seriesId}/pass-types/`) });
  const save = useMutation({ onSuccess: refresh, mutationFn: (body: PassType) => body.id
    ? staffRequest<PassType>(`/admin/event-pass-types/${body.id}/`, send("PATCH", body))
    : staffRequest<PassType>(`/admin/event-series/${seriesId}/pass-types/`, send("POST", body)) });
  return { rows, save };
}

export type DeskCollectInput = { terminal: boolean; method?: string; reference?: string };
export const collectAtDesk = (registrationId: number, body: DeskCollectInput) =>
  staffRequest<{ payment_id: number; payment_status: string; checkout_url: string }>(
    `/admin/event-registrations/${registrationId}/collect-payment/`, send("POST", body));
export const guestPayLink = (registrationId: number, sendEmail: boolean) =>
  staffRequest<{ pay_link: string; sent: boolean }>(`/admin/event-registrations/${registrationId}/pay-link/`,
    send("POST", { send: sendEmail }));
