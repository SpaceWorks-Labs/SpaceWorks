import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorText, Field, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { formatLocale } from "../../../lib/format";
import { devicesApi } from "../devicesApi";
import { labelPrintStatusLabel } from "./operationsLabels";

export type LabelCommand = {
  id: string; command_id: string; command_status: string; device_id: string; batch_id: number | null;
  request_id: string; batch_title_snapshot: string; item_count_snapshot: number; result: string;
  result_code: string; result_message: string; completed_at: string | null; created_at: string;
};
type Page<T> = { count: number; results: T[] };

const TONE: Record<string, "success" | "warn" | "danger" | "neutral"> = { succeeded: "success", failed: "danger", retryable_failed: "warn" };

/**
 * Sends a QR batch to an enrolled label printer (devices + QR print batches modules, MANAGE_QR).
 * Each press is one new request id; a reprint is just another send. The list shows what the
 * printer reported back.
 */
export function QrLabelPrinterSend({ makerspaceId, batchId, hasItems }: { makerspaceId: number; batchId: number; hasItems: boolean }) {
  const client = useQueryClient();
  const key = ["qr-batch-label-commands", batchId] as const;
  const printers = useQuery({ queryKey: ["devices", makerspaceId, "label-printers"], retry: false,
    queryFn: () => devicesApi.list(makerspaceId, 1) });
  const commands = useQuery({ queryKey: key, retry: false,
    queryFn: () => staffRequest<Page<LabelCommand> | LabelCommand[]>(`/admin/qr-print-batches/${batchId}/label-commands`) });
  const active = (printers.data?.results ?? []).filter(row => row.kind === "label_printer" && row.status === "active");
  const [device, setDevice] = useState("");
  const chosen = active.some(row => row.id === device) ? device : active[0]?.id ?? "";
  const send = useMutation({
    mutationFn: () => staffRequest<LabelCommand>(`/admin/qr-print-batches/${batchId}/label-commands`,
      { method: "POST", body: JSON.stringify({ device_id: chosen, request_id: crypto.randomUUID() }) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: key }); },
  });
  const rows = Array.isArray(commands.data) ? commands.data : commands.data?.results ?? [];
  const name = (id: string) => printers.data?.results.find(row => row.id === id)?.name ?? t`Label printer`;
  return <section className="rounded-md border border-line bg-surface p-3" aria-labelledby={`label-printer-${batchId}`}>
    <h3 id={`label-printer-${batchId}`} className="title-section mb-2">{t`Send to a label printer`}</h3>
    {printers.isSuccess && !active.length ? <p className="text-sm text-muted">{t`No active label printer is enrolled. Add one under Devices.`}</p> : null}
    {active.length ? <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
      <Field label={t`Label printer`}><select className="desk-input w-full" value={chosen} onChange={event => setDevice(event.target.value)}>
        {active.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
      <button type="button" className="desk-button" disabled={!chosen || !hasItems || send.isPending} onClick={() => send.mutate()}>
        {send.isPending ? t`Sending…` : rows.length ? t`Print again` : t`Send to printer`}</button>
    </div> : null}
    {printers.error ? <p className="text-sm text-muted">{t`You can't see this space's devices, so no label printer can be chosen.`}</p> : null}
    <ErrorText message={send.error?.message ?? commands.error?.message} />
    {rows.length ? <ul className="mt-3 grid gap-2" aria-label={t`Label print history`}>
      {rows.map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>{t`${name(row.device_id)} · ${row.item_count_snapshot} labels · ${new Date(row.created_at).toLocaleString(formatLocale())}`}
          {row.result_message ? ` · ${row.result_message}` : ""}</span>
        <StatusPill label={labelPrintStatusLabel(row.result || row.command_status)} tone={TONE[row.result] ?? "neutral"} />
      </li>)}
    </ul> : null}
  </section>;
}
