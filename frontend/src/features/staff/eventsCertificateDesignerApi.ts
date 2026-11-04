import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { PositionedElement } from "../../components/print-layout/positionedLayout";
import { staffRequest, staffRequestBlob } from "../../lib/api";
import { eventKeys } from "./eventsApiTypes";

export type CertificateParameters = {
  version: 1;
  page_width_mm: number;
  page_height_mm: number;
  grid_mm?: number;
  name_box: PositionedElement;
};
export type CertificateTemplateInput = { parameters: CertificateParameters; artwork_id: number | null };
export type CertificateTemplate = CertificateTemplateInput & { id: number | null; created_at: string | null };
export const certificateDesignerKeys = {
  template: (eventId: number) => [...eventKeys.detail(eventId), "certificate-template"] as const,
  artwork: (eventId: number, artworkId: number) => [...eventKeys.detail(eventId), "certificate-artwork", artworkId] as const,
};

/** The private artwork bytes, read with the staff session; artwork rows are immutable, so cache by id. */
export function useCertificateArtwork(eventId: number, artworkId: number | null) {
  return useQuery({ queryKey: certificateDesignerKeys.artwork(eventId, artworkId ?? 0), enabled: artworkId !== null,
    queryFn: () => staffRequestBlob(`/admin/events/${eventId}/certificate-artwork/${artworkId}/`), retry: false, staleTime: Infinity });
}

export function useEventCertificateTemplate(eventId: number) {
  return useQuery({ queryKey: certificateDesignerKeys.template(eventId),
    queryFn: () => staffRequest<CertificateTemplate>(`/admin/events/${eventId}/certificate-template/`) });
}

export function useSaveEventCertificateTemplate(makerspaceId: number, eventId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CertificateTemplateInput) => staffRequest<CertificateTemplate>(
      `/admin/events/${eventId}/certificate-template/`, { method: "POST", body: JSON.stringify(input) }),
    onSuccess: async (template) => {
      queryClient.setQueryData(certificateDesignerKeys.template(eventId), template);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: certificateDesignerKeys.template(eventId) }),
        queryClient.invalidateQueries({ queryKey: eventKeys.detail(eventId) }),
        queryClient.invalidateQueries({ queryKey: eventKeys.list(makerspaceId) }),
      ]);
    },
  });
}

export function usePreviewEventCertificate(eventId: number) {
  return useMutation({ mutationFn: (input: CertificateTemplateInput) => staffRequestBlob(
    `/admin/events/${eventId}/certificate-template/preview.pdf`, { method: "POST", body: JSON.stringify(input) }) });
}

export function useUploadCertificateArtwork(eventId: number) {
  return useMutation({ mutationFn: async (file: File) => {
    if (!["image/png", "image/jpeg"].includes(file.type) || file.size < 1 || file.size > 10 * 1024 * 1024) {
      throw new Error("Choose a PNG or JPEG image up to 10 MB.");
    }
    const upload = await staffRequest<{ id: number; upload_url: string; headers: Record<string, string> }>(
      `/admin/events/${eventId}/certificate-artwork/`, {
        method: "POST", body: JSON.stringify({ content_type: file.type, content_length: file.size }),
      });
    const response = await fetch(upload.upload_url, { method: "PUT", headers: upload.headers, body: file });
    if (!response.ok) throw new Error("Artwork upload failed. Select the image to try again.");
    return staffRequest<{ id: number }>(`/admin/events/${eventId}/certificate-artwork/${upload.id}/finalize/`, {
      method: "POST", body: JSON.stringify({}),
    });
  } });
}
