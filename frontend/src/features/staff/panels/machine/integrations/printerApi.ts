// Printer adapter (devices + machines + machine_service) and the machine-type integration
// foundation (`machines.integrations`). Every route needs MANAGE_DEVICES plus a machine scope
// that covers the machine or type; the server scopes every list.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../../../lib/api";

type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type PrinterBinding = { id: string; makerspace: number; device: string; machine: number | null; enabled: boolean;
  auto_apply_terminal: boolean; created_at: string; updated_at: string };
export type PrinterJobState = "awaiting" | "reported" | "applied" | "needs_review" | "cancelled";
export type PrinterJob = { id: string; device: string; machine: number | null; service_request: number | null;
  machine_name: string; service_request_name: string; external_job_id: string; state: PrinterJobState;
  telemetry_state: string; progress_percent: number | null; outcome: "completed" | "failed" | "" | null;
  actual_minutes: number | null; failure_reason: string; percent_complete: number | null; actual_grams: string | null;
  actual_quantity: string | null; reported_at: string | null; applied_at: string | null; created_at: string;
  consumptions: { machine_consumable: number | null; machine_consumable_id_snapshot: number; quantity: string }[] };
export type TypeIntegration = { id: string; makerspace: number; machine_type: number; kind: "printer_agent"; enabled: boolean;
  config_schema_version: number; created_at: string; updated_at: string };
export type IntegrationStatus = { device_id: string; device_name: string; machine_id: number; machine_name: string;
  last_seen_at: string | null; snapshot: null | { state: string; progress_percent: number | null; layer_current: number | null;
    layer_total: number | null; nozzle_temp_c: string | null; bed_temp_c: string | null; chamber_temp_c: string | null;
    spools: { slot: number; material: string; colour: string; remaining_percent: number | null }[]; observed_at: string } };

const json = (method: string, body?: unknown) => ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
export const printerKeys = {
  bindings: (space: number) => ["printer-bindings", space] as const,
  jobs: (space: number) => ["printer-jobs", space] as const,
  job: (id: string) => ["printer-job", id] as const,
  integrations: (space: number, typeId: number) => ["machine-type-integrations", space, typeId] as const,
  status: (space: number, typeId: number) => ["machine-type-integration-status", space, typeId] as const,
};

export function usePrinterBindings(space: number) {
  return useQuery({ queryKey: printerKeys.bindings(space),
    queryFn: () => staffRequest<Page<PrinterBinding>>(`/admin/makerspace/${space}/device-printer-bindings`) });
}

export function useBindingMutation(space: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (change: { create: { device_id: string; machine_id: number; enabled: boolean; auto_apply_terminal: boolean } }
      | { id: string; patch: Partial<Pick<PrinterBinding, "enabled" | "auto_apply_terminal">> } | { id: string; remove: true }): Promise<PrinterBinding | undefined> =>
      "create" in change ? staffRequest<PrinterBinding>(`/admin/makerspace/${space}/device-printer-bindings`, json("POST", change.create))
        : "remove" in change ? staffRequest<undefined>(`/admin/device-printer-bindings/${change.id}`, json("DELETE"))
          : staffRequest<PrinterBinding>(`/admin/device-printer-bindings/${change.id}`, json("PATCH", change.patch)),
    onSuccess: () => client.invalidateQueries({ queryKey: printerKeys.bindings(space) }),
  });
}

export function usePrinterJobs(space: number) {
  return useQuery({ queryKey: printerKeys.jobs(space),
    queryFn: () => staffRequest<Page<PrinterJob>>(`/admin/makerspace/${space}/printer-jobs`) });
}

export function usePrinterJob(id: string | null) {
  return useQuery({ queryKey: printerKeys.job(id ?? ""), enabled: id !== null,
    queryFn: () => staffRequest<PrinterJob>(`/admin/printer-jobs/${id}`) });
}

export function useJobMutation(space: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (change: { create: { binding_id: string; service_request_id: number; external_job_id: string } } | { apply: string }) =>
      "create" in change ? staffRequest<PrinterJob>(`/admin/makerspace/${space}/printer-jobs`, json("POST", change.create))
        : staffRequest<PrinterJob>(`/admin/printer-jobs/${change.apply}/apply`, json("POST", {})),
    onSuccess: (job) => {
      client.setQueryData(printerKeys.job(job.id), job);
      void client.invalidateQueries({ queryKey: printerKeys.jobs(space) });
    },
  });
}

export function useTypeIntegrations(space: number, typeId: number) {
  return useQuery({ queryKey: printerKeys.integrations(space, typeId),
    queryFn: () => staffRequest<TypeIntegration[]>(`/admin/makerspace/${space}/machine-types/${typeId}/integrations`) });
}

export function useIntegrationStatus(space: number, typeId: number, enabled: boolean) {
  return useQuery({ queryKey: printerKeys.status(space, typeId), enabled, refetchInterval: 30_000,
    queryFn: () => staffRequest<IntegrationStatus[]>(`/admin/makerspace/${space}/machine-types/${typeId}/integration-status`) });
}

export function useIntegrationMutation(space: number, typeId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (change: { create: true } | { id: string; enabled: boolean } | { id: string; remove: true }): Promise<TypeIntegration | undefined> =>
      "create" in change ? staffRequest<TypeIntegration>(`/admin/makerspace/${space}/machine-types/${typeId}/integrations`,
        json("POST", { kind: "printer_agent" }))
        : "remove" in change ? staffRequest<undefined>(`/admin/machine-type-integrations/${change.id}`, json("DELETE"))
          : staffRequest<TypeIntegration>(`/admin/machine-type-integrations/${change.id}`, json("PATCH", { enabled: change.enabled })),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: printerKeys.integrations(space, typeId) }),
      client.invalidateQueries({ queryKey: printerKeys.status(space, typeId) })]),
  });
}
