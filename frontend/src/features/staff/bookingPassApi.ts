import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest, staffRequestBlob } from "../../lib/api";
import type { BookingPassTemplate } from "../../generated/api";

export type { BookingPassTemplate };
export const bookingPassKey = (makerspaceId: number, spaceId: number) =>
  ["booking-pass-template", makerspaceId, spaceId] as const;
const basePath = (spaceId: number) => `/admin/spaces/${spaceId}/`;

export function useBookingPassDesigner(makerspaceId: number, spaceId: number) {
  const client = useQueryClient();
  const key = bookingPassKey(makerspaceId, spaceId);
  const query = useQuery({ queryKey: key, queryFn: () =>
    staffRequest<BookingPassTemplate>(basePath(spaceId) + "pass-template/"), retry: false });
  const save = useMutation({ mutationFn: (template: BookingPassTemplate) =>
    staffRequest<BookingPassTemplate>(basePath(spaceId) + "pass-template/", {
      method: "PUT", body: JSON.stringify(template),
    }), onSuccess: async () => {
      await Promise.all([client.invalidateQueries({ queryKey: key }),
        client.invalidateQueries({ queryKey: ["booking-space", spaceId] }),
        client.invalidateQueries({ queryKey: ["bookings", makerspaceId] })]);
    } });
  const preview = useMutation({ mutationFn: (template: BookingPassTemplate) =>
    staffRequestBlob(basePath(spaceId) + "pass-preview/", { method: "POST", body: JSON.stringify(template) }) });
  return { query, save, preview };
}

export function downloadPass(blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "booking-pass.pdf";
  link.click();
  URL.revokeObjectURL(url);
}

export function usePrintBookingPass(spaceId: number, bookingId: number) {
  // Actual PDFs are downloaded directly; never retained in the query cache or
  // shared with confirmation PNGs or template/sample previews.
  return useMutation({ mutationFn: async () => downloadPass(await staffRequestBlob(
    basePath(spaceId) + `arrival/${bookingId}/pass/`, { method: "POST", body: "{}" },
  )) });
}
