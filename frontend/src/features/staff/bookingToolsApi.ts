import { useMutation } from "@tanstack/react-query";
import type { ApiPath } from "../../generated/api";
import { staffRequest } from "../../lib/api";
import type { CustomAnswers } from "../forms/customFormTypes";
import { useSpaceInvalidation, type BookableSpace, type Booking } from "./bookingsApi";

const DETAILS: ApiPath = "/api/v1/admin/bookings/{id}/details/";
const TIME: ApiPath = "/api/v1/admin/bookings/{id}/time/";
const CLONE: ApiPath = "/api/v1/admin/spaces/{id}/clone/";
const pathFor = (path: ApiPath, id: number) => path.replace("/api/v1", "").replace("{id}", String(id));

export function useEditBooking(makerspaceId: number, spaceId: number, bookingId: number) {
  const invalidate = useSpaceInvalidation(makerspaceId, spaceId);
  return useMutation({
    mutationFn: (payload: { kind: "details"; note?: string; custom_answers?: CustomAnswers } | { kind: "time"; starts_at: string; ends_at: string; price_confirmation?: string }) => {
      const { kind, ...body } = payload;
      return staffRequest<Booking>(pathFor(kind === "details" ? DETAILS : TIME, bookingId), {
        method: kind === "details" ? "PATCH" : "POST", body: JSON.stringify(body),
      });
    }, onSuccess: invalidate,
  });
}

export function useCloneBookingSpace(makerspaceId: number, spaceId: number) {
  const invalidate = useSpaceInvalidation(makerspaceId, spaceId);
  return useMutation({
    mutationFn: (copyRules: boolean) => staffRequest<BookableSpace>(pathFor(CLONE, spaceId), {
      method: "POST", body: JSON.stringify({ copy_booking_rules: copyRules }),
    }), onSuccess: invalidate,
  });
}
