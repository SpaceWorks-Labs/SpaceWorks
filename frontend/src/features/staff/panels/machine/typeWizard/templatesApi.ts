import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../../../lib/api";
import { machineKeys } from "../../../machinesApi";
import type { ConsumableDefinition } from "./consumablesApi";

export type IntakeFieldSpec = { key: string; label: string; type: "text" | "number" | "integer" | "choice" | "boolean"; required?: boolean; choices?: string[]; min?: number; max?: number };
export type MaintenanceSpec = { title: string; trigger: "usage_hours" | "job_count" | "days"; interval: number };
export type TemplateSpec = {
  version: 1;
  basics: { metering_unit: "minutes" | "weight" | "volume" | "length" | "count"; requires_booking: boolean; is_public: boolean };
  consumables: Partial<ConsumableDefinition>[];
  intake_fields: IntakeFieldSpec[];
  pricing: { charge_by: "time" | "material" | "job" | "none" };
  access: { open_to_all_members: boolean; supervised: boolean };
  bookings: { bookable: boolean; slot_minutes?: number; buffer_minutes?: number; requires_approval?: boolean };
  safety: { idle_auto_off_minutes?: number; max_session_minutes?: number; area_clear_required?: boolean; filter_ok_required?: boolean };
  maintenance: MaintenanceSpec[];
  job: { accepts_job_requests: boolean; runs_unattended: boolean };
  notifications: { job_finished: boolean; job_failed: boolean; low_stock: boolean };
  documents: { training_notes: string };
  sources?: number[];
};
export type TypeTemplate = { id: number | null; key: string; name: string; description: string; category: string; icon: string; spec: TemplateSpec;
  is_builtin: boolean; customised: boolean; based_on: string | null; is_active: boolean };
export type TemplateInput = Pick<TypeTemplate, "key" | "name" | "description" | "category" | "icon" | "spec" | "is_active">;
export type Prefill = Pick<TemplateSpec, "pricing" | "access" | "bookings" | "safety" | "maintenance" | "job" | "notifications" | "documents">;
export type ApplyResult = { machine_type_id: number; created_type: boolean; template_key: string; consumables_added: string[]; consumables_skipped: string[]; prefill: Prefill };
export type ApplyBody = { machine_type_id?: number | null; name?: string; slug?: string };

const root = (makerspaceId: number) => `/admin/makerspaces/${makerspaceId}/machine-type-templates`;
const send = (method: string, body?: unknown) => ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
export const templateKeys = { all: (makerspaceId: number) => ["machine-type-templates", makerspaceId] as const };

export function useTemplates(makerspaceId: number, includeInactive = false, enabled = true) {
  return useQuery({ queryKey: [...templateKeys.all(makerspaceId), includeInactive], enabled, retry: false,
    queryFn: () => staffRequest<TypeTemplate[]>(`${root(makerspaceId)}${includeInactive ? "?include_inactive=1" : ""}`) });
}

export function useSaveTemplate(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: (body: TemplateInput) => staffRequest<TypeTemplate>(root(makerspaceId), send("POST", body)),
    onSuccess: () => client.invalidateQueries({ queryKey: templateKeys.all(makerspaceId) }) });
}

export function useDeleteTemplate(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: (key: string) => staffRequest<unknown>(`${root(makerspaceId)}/${encodeURIComponent(key)}`, send("DELETE")),
    onSuccess: () => client.invalidateQueries({ queryKey: templateKeys.all(makerspaceId) }) });
}

export function useApplyTemplate(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: ({ key, body }: { key: string; body: ApplyBody }) =>
    staffRequest<ApplyResult>(`${root(makerspaceId)}/${encodeURIComponent(key)}/apply`, send("POST", body)),
  onSuccess: async () => { await Promise.all([client.invalidateQueries({ queryKey: machineKeys.types(makerspaceId) }),
    client.invalidateQueries({ queryKey: ["machine-type-consumables", makerspaceId] })]); } });
}
