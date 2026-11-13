import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { patch, post, type Page } from "./parityRequest";

export type DrillSettings = { restore_drill_interval_days: number; archive_ready_notice_enabled: boolean };
export type DrillOverview = { configured: boolean; key_rotation: string; settings: DrillSettings };
export type DrillReport = {
  id: number; makerspace_id: number; makerspace_name: string | null; started_at: string; finished_at: string | null;
  outcome: "passed" | "failed"; error_code: string;
  checks: { row_total?: number; objects_verified?: number; [check: string]: unknown };
};
export type DrillQueued = { makerspace_id: number; archive_id: string; status: "queued" };

const BASE = "/admin/platform/restore-drills";
const settingsKey = ["platform-restore-drill-settings"] as const;
const reportsKey = ["platform-restore-drills"] as const;

export function useDrillOverview() {
  return useQuery({ queryKey: settingsKey, queryFn: () => staffRequest<DrillOverview>(`${BASE}/settings`, {}, "platform") });
}

export function useSaveDrillSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<DrillSettings>) => patch<DrillSettings>(`${BASE}/settings`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: settingsKey }),
  });
}

export function useDrillReports(page: number) {
  return useQuery({ queryKey: [...reportsKey, page], queryFn: () => staffRequest<Page<DrillReport>>(`${BASE}?page=${page}`, {}, "platform") });
}

/** Queues a drill of the space's newest restorable backup; its report appears in the list when it finishes. */
export function useRunDrill() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (makerspaceId: number) => post<DrillQueued>(BASE, { makerspace_id: makerspaceId }),
    onSuccess: () => client.invalidateQueries({ queryKey: reportsKey }),
  });
}
