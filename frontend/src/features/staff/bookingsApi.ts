import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiPath } from "../../generated/api";
import { staffRequest } from "../../lib/api";
import type { CustomAnswerSnapshot, CustomFormSchema } from "../forms/customFormTypes";
import type { PaymentSummary } from "./PaymentReconcileActions";
import type { BookingDeparture } from "../bookings/DepartureForm";

export type BookingStatus = "pending" | "confirmed" | "rejected" | "cancelled" | "completed" | "no_show";
export type BookableSpace = {
  id: number;
  clone_enabled?: boolean;
  staff_tools_enabled?: boolean;
  can_copy_booking_rules?: boolean;
  cancellation_cutoff_hours?: number;
  report_features?: string[];
  recurring_enabled?: boolean;
  staff_grants_enabled?: boolean;
  checkin_enabled?: boolean;
  passes_enabled?: boolean;
  website_enabled?: boolean;
  embed_enabled?: boolean;
  broadcasts_enabled?: boolean;
  staff_permissions?: string[];
  can_manage_grants?: boolean;
  public_token: string;
  makerspace_id: number;
  name: string;
  kind: "dev_room" | "bench" | "meeting" | "other" | "machine";
  description: string;
  capacity: number;
  location: string;
  image_url: string;
  is_public: boolean;
  show_public_availability: boolean;
  show_public_booker_names: boolean;
  approval_mode: "instant" | "approve";
  payment_amount: string;
  custom_form: CustomFormSchema;
  requester_notifications_enabled: boolean | null;
  machine_type?: number | null;
  /** Machine time booking (`machines.time_booking`): this resource is one machine's time. */
  machine?: number | null;
  effective_requester_notifications_enabled: boolean;
  is_active: boolean;
  created_by_id: number | null;
  created_at: string;
  updated_at: string;
};

export type BookableSpacePayload = Pick<BookableSpace,
  "name" | "kind" | "description" | "capacity" | "location" | "is_public" |
  "show_public_availability" | "show_public_booker_names" |
  "custom_form" | "requester_notifications_enabled" | "payment_amount" | "machine_type" | "machine"
>;

export type Booking = {
  id: number;
  public_token: string;
  space_id: number;
  name: string;
  email: string;
  phone: string;
  starts_at: string;
  ends_at: string;
  status: BookingStatus;
  arrived_at?: string | null;
  note: string;
  custom_answers: CustomAnswerSnapshot | null;
  payment: PaymentSummary | null;
  cancelled_at?: string | null;
  status_before_cancel?: string;
  restore_until?: string | null;
  created_at: string;
  /** Phase 2 (hand-typed until the client is regenerated). */
  space_name?: string;
  decision_reason?: string;
  departed_at?: string | null;
  departures?: BookingDeparture[];
  open_issue_id?: number | null;
  /** L15 (#159): the price frozen when a booking awaiting approval was requested. */
  requested_price?: { total?: string | null; currency?: string | null; discount_total?: string | null } | null;
  /** Decision 216: the event this booking holds the room for; the title only when this viewer may see it. */
  linked_event?: LinkedEventLabel | null;
  /** Decision 223 (h): a staff-only house booking (no member booker, no charge). */
  is_house?: boolean;
  /** Decision 223 P2: the organization a staff organization booking was made for. */
  organization_name?: string | null;
  /** Decision 242 (BK2): the requester's account, for the member link; null for house/guest bookings. */
  member_id?: number | null;
};
export type LinkedEventLabel = { kind: "event" | "reserved"; event_id?: number; title?: string;
  event_status?: "draft" | "published" | "cancelled" | "completed" };

export type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type BookingFilters = { status?: BookingStatus | ""; starts_at?: string; ends_at?: string; booking_id?: number };

const SPACE_LIST_PATH: ApiPath = "/api/v1/admin/makerspaces/{makerspace_id}/spaces/";
const SPACE_DETAIL_PATH: ApiPath = "/api/v1/admin/spaces/{id}/";
const SPACE_DEACTIVATE_PATH: ApiPath = "/api/v1/admin/spaces/{id}/deactivate/";
const SPACE_BOOKINGS_PATH: ApiPath = "/api/v1/admin/spaces/{id}/bookings/";
const ACTION_PATHS = {
  restore: "/api/v1/admin/bookings/{id}/restore/",
  approve: "/api/v1/admin/bookings/{id}/approve/",
  reject: "/api/v1/admin/bookings/{id}/reject/",
  cancel: "/api/v1/admin/bookings/{id}/cancel/",
  complete: "/api/v1/admin/bookings/{id}/complete/",
  "no-show": "/api/v1/admin/bookings/{id}/no-show/",
} satisfies Record<string, ApiPath>;
export type BookingAction = keyof typeof ACTION_PATHS;

function staffPath(path: ApiPath, replacements: Record<string, number>) {
  return Object.entries(replacements).reduce(
    (value, [key, replacement]) => value.replace("{" + key + "}", String(replacement)),
    path.replace("/api/v1", ""),
  );
}

export const bookingKeys = {
  all: (makerspaceId: number) => ["bookings", makerspaceId] as const,
  spaces: (makerspaceId: number) => [...bookingKeys.all(makerspaceId), "spaces"] as const,
  detail: (spaceId: number) => ["booking-space", spaceId] as const,
  bookings: (spaceId: number) => ["booking-space", spaceId, "bookings"] as const,
  availability: (spaceId: number) => ["booking-space", spaceId, "availability"] as const,
};

export function useBookableSpaces(makerspaceId: number, page = 1, query = "") {
  return useQuery({
    queryKey: [...bookingKeys.spaces(makerspaceId), page, query],
    queryFn: () => staffRequest<Paginated<BookableSpace>>(staffPath(SPACE_LIST_PATH, { makerspace_id: makerspaceId }) + "?" + (query || "page=" + page)),
  });
}

export function useBookableSpace(spaceId: number) {
  return useQuery({
    queryKey: bookingKeys.detail(spaceId),
    queryFn: () => staffRequest<BookableSpace>(staffPath(SPACE_DETAIL_PATH, { id: spaceId })),
  });
}

export function useSpaceBookings(spaceId: number, filters: BookingFilters, page = 1, ordering = "starts_at", enabled = true) {
  const timestamp = (value: string) => { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toISOString(); };
  const query = new URLSearchParams({ page: String(page), ordering });
  if (filters.status) query.set("status", filters.status);
  if (filters.booking_id) query.set("booking_id", String(filters.booking_id));
  if (filters.starts_at) query.set("starts_at", timestamp(filters.starts_at));
  if (filters.ends_at) query.set("ends_at", timestamp(filters.ends_at));
  return useQuery({
    enabled,
    queryKey: [...bookingKeys.bookings(spaceId), filters.status ?? "", filters.starts_at ?? "", filters.ends_at ?? "", filters.booking_id ?? "", page, ordering],
    queryFn: () => staffRequest<Paginated<Booking>>(staffPath(SPACE_BOOKINGS_PATH, { id: spaceId }) + "?" + query),
  });
}

export function useSpaceInvalidation(makerspaceId: number, spaceId?: number) {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: bookingKeys.spaces(makerspaceId) }),
      queryClient.invalidateQueries({ queryKey: ["public-spaces"] }),
      queryClient.invalidateQueries({ queryKey: ["public-booking-resource"] }),
      queryClient.invalidateQueries({ queryKey: ["public-website-image"] }),
      queryClient.invalidateQueries({ queryKey: ["booking-discover"] }),
      queryClient.invalidateQueries({ queryKey: ["operations-report"] }),
      queryClient.invalidateQueries({ queryKey: ["member"] }),
      queryClient.invalidateQueries({ queryKey: ["bookings", "accessible"] }),
      queryClient.invalidateQueries({ queryKey: ["fablab-report", "booking-utilization"] }),
      ...(spaceId === undefined ? [] : [
        queryClient.invalidateQueries({ queryKey: bookingKeys.detail(spaceId) }),
        queryClient.invalidateQueries({ queryKey: bookingKeys.bookings(spaceId) }),
        queryClient.invalidateQueries({ queryKey: bookingKeys.availability(spaceId) }),
        queryClient.invalidateQueries({ queryKey: ["public-space-availability"] }),
      ]),
    ]);
  };
}

export function useCreateBookableSpace(makerspaceId: number) {
  const invalidate = useSpaceInvalidation(makerspaceId);
  return useMutation({
    mutationFn: (payload: BookableSpacePayload) => staffRequest<BookableSpace>(
      staffPath(SPACE_LIST_PATH, { makerspace_id: makerspaceId }),
      { method: "POST", body: JSON.stringify(payload) },
    ),
    onSuccess: invalidate,
  });
}

export function useUpdateBookableSpace(makerspaceId: number, spaceId: number) {
  const invalidate = useSpaceInvalidation(makerspaceId, spaceId);
  return useMutation({
    mutationFn: (payload: Partial<BookableSpacePayload>) => staffRequest<BookableSpace>(
      staffPath(SPACE_DETAIL_PATH, { id: spaceId }),
      { method: "PATCH", body: JSON.stringify(payload) },
    ),
    onSuccess: invalidate,
  });
}

export function useDeactivateBookableSpace(makerspaceId: number, spaceId: number) {
  const invalidate = useSpaceInvalidation(makerspaceId, spaceId);
  return useMutation({
    mutationFn: () => staffRequest<BookableSpace>(
      staffPath(SPACE_DEACTIVATE_PATH, { id: spaceId }),
      { method: "POST", body: JSON.stringify({}) },
    ),
    onSuccess: invalidate,
  });
}

export function useBookingAction(makerspaceId: number, spaceId?: number) {
  const queryClient = useQueryClient();
  const invalidate = useSpaceInvalidation(makerspaceId, spaceId);
  return useMutation({
    // Reject requires a reason and cancel accepts one; both are shown to the requester.
    mutationFn: ({ bookingId, action, reason }: { bookingId: number; action: BookingAction; reason?: string }) => staffRequest<Booking>(
      staffPath(ACTION_PATHS[action], { id: bookingId }),
      { method: "POST", body: JSON.stringify((action === "reject" || action === "cancel") && reason ? { reason } : {}) },
    ),
    onSuccess: async () => { await invalidate(); await queryClient.invalidateQueries({ queryKey: ["booking-queue"] }); },
  });
}
