import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../../../lib/api";
import { machineKeys } from "../../../machinesApi";

export type WorkOrderStatus = "open" | "in_progress" | "on_hold" | "done" | "cancelled";
export type WorkOrderPriority = "low" | "normal" | "high" | "urgent";
export type WorkOrder = {
  id: number; subject_type: "machine" | "inventory_product" | "inventory_asset" | "bookable_space"; subject_id: number;
  subject_label: string; title: string; description: string; priority: WorkOrderPriority; status: WorkOrderStatus;
  takes_machine_down: boolean; due_on: string | null; assignee_id: number | null; resolution: string;
  schedule_id: number | null; log_id: number | null; created_at: string; updated_at: string;
  started_at: string | null; closed_at: string | null;
};
export type WorkOrderInput = {
  subject_type: "machine"; subject_id: number; title: string; description?: string; priority: WorkOrderPriority;
  due_on?: string | null; takes_machine_down?: boolean;
};

export const OPEN_STATUSES: WorkOrderStatus[] = ["open", "in_progress", "on_hold"];
export const STATUS_LABELS: Record<WorkOrderStatus, string> = { open: "Open", in_progress: "In progress", on_hold: "On hold", done: "Done", cancelled: "Cancelled" };
export const PRIORITY_LABELS: Record<WorkOrderPriority, string> = { low: "Low", normal: "Normal", high: "High", urgent: "Urgent" };

export const workOrderKeys = {
  all: ["work-orders"] as const,
  list: (makerspaceId: number, filter: string) => ["work-orders", makerspaceId, filter] as const,
};

/** `filter` is the raw query string (`status=open,in_progress&machine=4`); the server scopes rows to the actor. */
export function useWorkOrders(makerspaceId: number, filter = "", enabled = true) {
  return useQuery({ queryKey: workOrderKeys.list(makerspaceId, filter), enabled,
    queryFn: () => staffRequest<WorkOrder[]>(`/admin/makerspaces/${makerspaceId}/work-orders${filter ? `?${filter}` : ""}`) });
}

function useRefresh() {
  const client = useQueryClient();
  // A work order that takes its machine down changes that machine's status and downtime too.
  return () => Promise.all([
    client.invalidateQueries({ queryKey: workOrderKeys.all }),
    client.invalidateQueries({ queryKey: machineKeys.all }),
    client.invalidateQueries({ queryKey: ["machine"] }),
    client.invalidateQueries({ queryKey: ["machine-downtime"] }),
  ]);
}

export function useCreateWorkOrder(makerspaceId: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (input: WorkOrderInput) => staffRequest<WorkOrder>(`/admin/makerspaces/${makerspaceId}/work-orders`, { method: "POST", body: JSON.stringify(input) }),
    onSuccess: () => { void refresh(); },
  });
}

export function useMoveWorkOrder() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; status: Exclude<WorkOrderStatus, "open">; resolution?: string; cost?: string | null; parts_note?: string }) =>
      staffRequest<WorkOrder>(`/admin/work-orders/${id}/status`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => { void refresh(); },
  });
}

export function useAssignWorkOrder() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, assignee_id }: { id: number; assignee_id: number | null }) =>
      staffRequest<WorkOrder>(`/admin/work-orders/${id}/assign`, { method: "POST", body: JSON.stringify({ assignee_id }) }),
    onSuccess: () => { void refresh(); },
  });
}

export function priorityTone(priority: WorkOrderPriority) {
  return priority === "urgent" ? "danger" as const : priority === "high" ? "warn" as const : "neutral" as const;
}
export function statusTone(status: WorkOrderStatus) {
  return status === "in_progress" ? "accent" as const : status === "on_hold" ? "warn" as const : status === "done" ? "success" as const : "neutral" as const;
}
