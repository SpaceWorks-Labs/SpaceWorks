import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { IncludedHoursSummary } from "../payments/IncludedHoursLine";

import { staffRequest } from "../../lib/api";
import type { CustomAnswers } from "../forms/customFormTypes";
import { bookingKeys, type Booking, type Paginated } from "./bookingsApi";

export type RecurringBookingResult = { occurrences: { occurrence: number; booking_id: number | null; status: string; detail: string; starts_at: string; ends_at: string }[] };

export type StaffBookingPayload = {
  count?: number;
  interval_weeks?: number;
  /** Omitted only for a house booking. */
  member_id?: number;
  /** Decision 223 (h): a staff-only house booking -- no member booker, no charge, no plan hours. */
  house?: boolean;
  starts_at: string;
  ends_at: string;
  note: string;
  certification_override_reason?: string;
  custom_answers?: CustomAnswers;
  /** Digest from the staff price preview; 409 `price_changed` creates nothing (decision 216). */
  price_confirmation?: string;
};

/** The room price a staff booking will charge, bound to room, member, window and charge mode. */
export type StaffBookingQuote = {
  charges: "tracked" | "off";
  quote: { currency: string; total: string; discount_total: string; included_hours?: IncludedHoursSummary | null } | null;
  price_confirmation: string;
  /** Decision 221(d): plan hours this booking uses; null when none (also sent when charges are off). */
  included_hours?: IncludedHoursSummary | null;
};

export function previewStaffBookingPrice(spaceId: number, body: { member_id: number; starts_at: string; ends_at: string }) {
  return staffRequest<StaffBookingQuote>(`/admin/spaces/${spaceId}/bookings/quote/`, {
    method: "POST", body: JSON.stringify(body),
  });
}

export function getBookingMachineTypes(makerspaceId: number, page: number) {
  return staffRequest<Paginated<{ id: number; name: string }>>(
    `/admin/makerspaces/${makerspaceId}/booking-machine-types/?page=${page}`,
  );
}

export function useBookingEligibleMembers(spaceId: number, page: number) {
  return useQuery({
    queryKey: ["booking-eligible-members", spaceId, page],
    queryFn: () => staffRequest<Paginated<{ member_id: number; display_name: string }>>(
      `/admin/spaces/${spaceId}/eligible-members/?page=${page}`,
    ),
  });
}

export function useStaffCreateBooking(makerspaceId: number, spaceId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StaffBookingPayload) => staffRequest<Booking | RecurringBookingResult>(
      `/admin/spaces/${spaceId}/${payload.count ? "recurring-bookings" : "bookings"}/`, { method: "POST", body: JSON.stringify(payload) },
    ),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: bookingKeys.spaces(makerspaceId) }),
        queryClient.invalidateQueries({ queryKey: bookingKeys.bookings(spaceId) }),
        queryClient.invalidateQueries({ queryKey: ["public-space-availability"] }),
        queryClient.invalidateQueries({ queryKey: ["operations-report"] }),
      ]);
    },
  });
}
