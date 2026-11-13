import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest, memberRequestBlob } from "../../lib/api";
import { personalRecipientKey } from "../notifications/personalQueryKeys";
import type { BookingConfirmation } from "../../generated/api";

export const confirmationPath = (slug: string, token: string) =>
  `/public/${encodeURIComponent(slug)}/my-bookings/${encodeURIComponent(token)}/`;

export function useBookingConfirmation(slug: string, token: string) {
  const recipient = personalRecipientKey();
  const key = ["member", slug, "booking-confirmation", recipient, token];
  const client = useQueryClient();
  const detail = useQuery({ queryKey: key, queryFn: () => memberRequest<BookingConfirmation>(confirmationPath(slug, token) + "confirmation/"),
    retry: false, staleTime: 0, gcTime: 0, meta: { persist: false } });
  const rotate = useMutation({ mutationFn: () => memberRequest<BookingConfirmation>(confirmationPath(slug, token) + "rotate-checkin/", { method: "POST", body: "{}" }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: key }); } });
  return { detail, rotate };
}

export async function downloadBookingFile(slug: string, token: string, kind: "png" | "ics" | "pdf") {
  const blob = await memberRequestBlob(confirmationPath(slug, token) + (kind === "png" ? "confirmation.png" : kind === "pdf" ? "pass.pdf" : "calendar.ics"));
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `booking.${kind}`;
  link.click();
  URL.revokeObjectURL(url);
}
