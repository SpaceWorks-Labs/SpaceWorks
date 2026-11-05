import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { MachineServiceRequest } from "../../../../generated/api";
import { staffRequest } from "../../../../lib/api";
import { machineKeys } from "../../machinesApi";
import { poolQueryKey } from "./servicePools";

/** The staff job row plus the uniform job-flow columns (#140-#142) the generated schema does not carry yet. */
export type StaffJob = Omit<MachineServiceRequest, "status"> & {
  status: MachineServiceRequest["status"] | "changes_requested" | "quoted" | "uncollected";
  queued_at?: string | null; urgent?: boolean; urgent_reason?: string; needed_by?: string | null; copies?: number;
  own_material?: boolean; material_note?: string; member_estimate_minutes?: number | null;
  preassigned_machine_id?: number | null; batch_id?: number | null; changes_requested_at?: string | null;
  changes_code?: string; changes_message?: string; member_note?: string; reject_code?: string;
  quote_snapshot?: { total?: string; currency?: string } | null; quoted_at?: string | null;
  quote_expires_at?: string | null; quote_approved_at?: string | null; prepay?: boolean; fail_code?: string;
  fail_fault?: string; failure_outcome?: string; auto_requeue_count?: number; pickup_location?: string;
  pickup_reminders_sent?: number; uncollected_at?: string | null; collected_by_name?: string; reprint_of_id?: number | null;
  /** #142 OQ-6: why the job may miss its needed-by date (a flag only; empty when on track). */
  at_risk_reasons?: string[];
};

export type BoardLane = { machine_id: number; machine_name: string; status: string; locked_out: boolean; running: StaffJob[]; assigned: StaffJob[] };
export type JobBoard = {
  machine_type_id: number; lanes: BoardLane[]; queue: StaffJob[]; review: StaffJob[]; waiting_on_member: StaffJob[];
  ready: StaffJob[]; overdue_pickup_ids: number[]; no_show_member_ids: number[];
};

export type JobSettings = {
  accepts_job_requests: boolean; quote_mode: "auto" | "off" | "above" | "always"; quote_above_amount: string | null;
  payment_timing: "completion" | "prepay"; member_fault_charge: "none" | "material_only" | "full";
  max_open_jobs: number | null; max_job_minutes: number | null; runs_unattended: boolean | null; file_groups: string[];
};

export type BoardAction = "accept" | "reject" | "start" | "complete" | "fail" | "collect" | "quote" | "request-changes"
  | "queue-now" | "reorder" | "urgent" | "assign" | "uncollected";

export const jobBoardKey = (makerspaceId: number, typeId: number) => ["machine-job-board", makerspaceId, typeId] as const;
export const jobSettingsKey = (makerspaceId: number, typeId: number) => ["machine-job-settings", makerspaceId, typeId] as const;

/** `code` of a structured API error, read by shape so a mocked api module cannot break it. */
export function errorCode(error: unknown): string | undefined {
  const code = (error as { code?: unknown } | null)?.code;
  return typeof code === "string" ? code : undefined;
}

/** Every cache a job transition can change: the board, the list console, pools and machine status. */
export function useJobInvalidation(makerspaceId: number, typeId: number) {
  const client = useQueryClient();
  return () => Promise.all([
    client.invalidateQueries({ queryKey: jobBoardKey(makerspaceId, typeId) }),
    client.invalidateQueries({ queryKey: ["machine-service-requests", makerspaceId, typeId] }),
    client.invalidateQueries({ queryKey: ["operations-report"] }),
    client.invalidateQueries({ queryKey: poolQueryKey(makerspaceId) }),
    client.invalidateQueries({ queryKey: machineKeys.list(makerspaceId) }),
  ]);
}

export function useJobBoard(makerspaceId: number, typeId: number, enabled: boolean) {
  return useQuery({
    queryKey: jobBoardKey(makerspaceId, typeId), enabled,
    queryFn: () => staffRequest<JobBoard>(`/admin/makerspaces/${makerspaceId}/machine-service/board?machine_type_id=${typeId}`),
  });
}

export function useJobAction(makerspaceId: number, typeId: number) {
  const invalidate = useJobInvalidation(makerspaceId, typeId);
  return useMutation({
    mutationFn: ({ id, action, body = {} }: { id: number; action: BoardAction; body?: object }) =>
      staffRequest<StaffJob>(`/admin/machine-service/requests/${id}/${action}`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => { void invalidate(); },
  });
}

export type BatchStartBody = { job_ids: number[]; machine_id: number; plans?: Record<string, object>; note?: string };
export type BatchCompleteBody = { actual_minutes: number; actual_quantity?: string; splits?: { minutes?: Record<string, number>; quantity?: Record<string, string> }; pickup_location?: string };

export function useBatchStart(makerspaceId: number, typeId: number) {
  const invalidate = useJobInvalidation(makerspaceId, typeId);
  return useMutation({
    mutationFn: (body: BatchStartBody) => staffRequest<{ batch_id: number; jobs: StaffJob[] }>(
      `/admin/makerspaces/${makerspaceId}/machine-service/batches`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => { void invalidate(); },
  });
}

export function useBatchComplete(makerspaceId: number, typeId: number) {
  const invalidate = useJobInvalidation(makerspaceId, typeId);
  return useMutation({
    mutationFn: ({ batchId, body }: { batchId: number; body: BatchCompleteBody }) => staffRequest<{ batch_id: number; jobs: StaffJob[] }>(
      `/admin/machine-service/batches/${batchId}/complete`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => { void invalidate(); },
  });
}

const settingsPath = (makerspaceId: number, typeId: number) => `/admin/makerspaces/${makerspaceId}/machine-types/${typeId}/job-settings`;

export function useJobSettings(makerspaceId: number, typeId: number, enabled: boolean) {
  return useQuery({ queryKey: jobSettingsKey(makerspaceId, typeId), enabled, retry: false,
    queryFn: () => staffRequest<JobSettings>(settingsPath(makerspaceId, typeId)) });
}

export function useSaveJobSettings(makerspaceId: number, typeId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<JobSettings>) => staffRequest<JobSettings>(settingsPath(makerspaceId, typeId), { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: (data) => client.setQueryData(jobSettingsKey(makerspaceId, typeId), data),
  });
}
