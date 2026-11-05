import { CommandSession } from '../../events/hackathonAdmission/transport';
import { useEffect, useRef } from "react";
import { sessionScope } from "../eventProgramme/sessionScope";
import type { PrintAccepted, PrintDetail } from "../../../generated/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest, staffRequestBlob } from "../../../lib/api";
import type { LayerDocument, LegacyDocument } from "./layout";
import type { DesignStock as Stock } from "./badgeStocks";

export type DesignInput = { parameters: LayerDocument; artwork_id: number | null };
export type CertificateDesign = { id: number | null; parameters: LayerDocument | LegacyDocument; artwork_id: number | null; event_version: number };
const key = (eventId: number) => ["events", "credentials", eventId, "certificate-design", ...sessionScope()] as const;

export function useDesign(eventId: number) {
  const commands = useRef(new CommandSession());
  const query = useQuery({ queryKey: key(eventId), queryFn: () => staffRequest<CertificateDesign>(`/admin/events/${eventId}/certificate-template/`) });
  const client = useQueryClient();
  const save = useMutation({ mutationFn: (input: DesignInput) => commands.current.send<CertificateDesign>(
    `/api/v1/admin/events/${eventId}/certificate-template/`, 'PUT', { ...input, expected_version: query.data?.event_version }, true),
  onSuccess: async (result) => { client.setQueryData(key(eventId), result); await Promise.all([client.invalidateQueries({ queryKey: key(eventId) }), client.invalidateQueries({ queryKey: ['event', eventId] }), client.invalidateQueries({ queryKey: ['event-badge-desk-design', eventId] })]); } });
  const preview = useMutation({ mutationFn: (input: DesignInput) => staffRequestBlob(
    `/admin/events/${eventId}/certificate-template/preview.pdf`, { method: "POST", body: JSON.stringify(input) }) });
  return { query, save, preview };
}

export type PrintJob = PrintAccepted;
export function useDeskPrint(eventId: number) {
  const client = useQueryClient();
  const running = useRef<AbortController | null>(null);
  const command = useRef<{ identity: string; operation: string; job?: PrintAccepted }>({ identity: '', operation: '' });
  useEffect(() => () => running.current?.abort(), []);
  return useMutation({ mutationFn: async (values: { registration_ids: number[]; expected_version: number;
    template_revision: number; stock: Stock; include_photo: boolean }) => {
    const identity = JSON.stringify(values);
    if (command.current.identity !== identity) command.current = { identity, operation: crypto.randomUUID() };
    running.current?.abort();
    const controller = new AbortController(); running.current = controller;
    const operation = command.current.operation;
    let job: PrintAccepted | PrintDetail = command.current.job ?? await staffRequest<PrintAccepted>(`/admin/events/${eventId}/badges/print-jobs/`, {
      method: 'POST', signal: controller.signal, headers: { 'Idempotency-Key': operation }, body: JSON.stringify({ ...values, operation_id: operation }),
    });
    command.current.job = job;
    for (let attempt = 0; job.state !== 'ready'; attempt++) {
      if (['failed', 'revoked', 'expired', 'cancelled'].includes(job.state)) throw new Error(`This print job is ${job.state}. Refresh the desk before printing again.`);
      if (attempt >= 30) throw new Error('The print job is still preparing. Retry to check this same job.');
      await new Promise<void>((resolve, reject) => {
        const aborted = () => { clearTimeout(timer); reject(new Error('Print request closed.')); };
        const timer = setTimeout(() => { controller.signal.removeEventListener('abort', aborted); resolve(); }, 1000);
        controller.signal.addEventListener('abort', aborted, { once: true });
        if (controller.signal.aborted) aborted();
      });
      job = await staffRequest<PrintDetail>(`/admin/events/${eventId}/badges/print-jobs/${job.job_id}/`, { signal: controller.signal });
    }
    const blob = await staffRequestBlob(`/admin/events/${eventId}/badges/print-jobs/${job.job_id}/download/`, { signal: controller.signal });
    return { blob, failures: (job.row_failures ?? []).filter((row): row is { registration_id: number; error_code: string } =>
      typeof row.registration_id === 'number' && typeof row.error_code === 'string') };
  }, onSuccess: async () => {
    command.current = { identity: '', operation: '' };
    await Promise.all([client.invalidateQueries({ queryKey: ['event-badge-desk-design', eventId] }), client.invalidateQueries({ queryKey: ['event', eventId] })]);
  } });
}

export function useBadgeDesignSave(eventId: number) {
  const commands = useRef(new CommandSession());
  return useMutation({ mutationFn: (values: { document: LayerDocument; stock: Stock; expected_version: number }) => commands.current.send<{
    id: number; document: LayerDocument; stock: Stock; event_version: number;
  }>(`/api/v1/admin/events/${eventId}/badges/designs/`, 'POST', values, true) });
}
