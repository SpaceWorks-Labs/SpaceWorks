import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest, staffRequestBlob } from "../../../lib/api";
import type { LayerDocument, LegacyDocument, Stock } from "./layout";

export type DesignInput = { parameters: LayerDocument; artwork_id: number | null };
export type CertificateDesign = { id: number | null; parameters: LayerDocument | LegacyDocument; artwork_id: number | null; event_version: number };
const key = (eventId: number) => ["events", "credentials", eventId, "certificate-design"] as const;

export function useDesign(eventId: number) {
  const query = useQuery({ queryKey: key(eventId), queryFn: () => staffRequest<CertificateDesign>(`/admin/events/${eventId}/certificate-template/`) });
  const client = useQueryClient();
  const save = useMutation({ mutationFn: (input: DesignInput) => staffRequest<CertificateDesign>(
    `/admin/events/${eventId}/certificate-template/`, { method: "PUT", body: JSON.stringify({ ...input,
      operation_id: crypto.randomUUID(), expected_version: query.data?.event_version }) }),
  onSuccess: async (result) => { client.setQueryData(key(eventId), result); await client.invalidateQueries({ queryKey: key(eventId) }); } });
  const preview = useMutation({ mutationFn: (input: DesignInput) => staffRequestBlob(
    `/admin/events/${eventId}/certificate-template/preview.pdf`, { method: "POST", body: JSON.stringify(input) }) });
  return { query, save, preview };
}

export type PrintJob = { job_id: number; state: string; status_url: string; row_failures?: { registration_id: number; error_code: string }[] };
export function useDeskPrint(eventId: number) {
  return useMutation({ mutationFn: async (values: { registration_ids: number[]; expected_version: number;
    template_revision: number; stock: Stock; include_photo: boolean }) => {
    const job = await staffRequest<PrintJob>(`/admin/events/${eventId}/badges/print-jobs/`, {
      method: "POST", body: JSON.stringify({ ...values, operation_id: crypto.randomUUID() }),
    });
    if (job.state !== "ready") throw new Error("Your print job is still being prepared. Open its status to retry.");
    const blob = await staffRequestBlob(`/admin/events/${eventId}/badges/print-jobs/${job.job_id}/download/`);
    return { blob, failures: job.row_failures ?? [] };
  } });
}

export function useBadgeDesignSave(eventId: number) {
  return useMutation({ mutationFn: (values: { document: LayerDocument; stock: Stock; expected_version: number }) => staffRequest<{
    id: number; document: LayerDocument; stock: Stock; event_version: number;
  }>(`/admin/events/${eventId}/badges/designs/`, { method: "POST", body: JSON.stringify({ ...values, operation_id: crypto.randomUUID() }) }) });
}
