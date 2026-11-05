import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { Page } from "../../events/hackathonGallery/types";
import { sessionScope } from "../eventProgramme/sessionScope";
import type { Extension, OrganizerProject, Shortlist, ShortlistPlan, ShortlistSelection, StagePlan } from "./types";

export const stagesKey = (eventId: number) => ["staff-submission-stages", eventId, ...sessionScope()] as const;
const base = (eventId: number) => `/admin/events/${eventId}/submission-stages/`;

/** A command body with a fresh operation id, echoed in the Idempotency-Key header (PrivateSubmissionView). */
export function sendCommand<T>(path: string, method: "POST" | "PUT", fields: Record<string, unknown>) {
  const operation = crypto.randomUUID();
  return staffRequest<T>(path, { method, headers: { "Idempotency-Key": operation },
    body: JSON.stringify({ ...fields, operation_id: operation }) });
}

export function useStagePlan(eventId: number, enabled = true) {
  return useQuery({ queryKey: stagesKey(eventId), enabled, retry: false,
    queryFn: () => staffRequest<StagePlan>(base(eventId)) });
}

export function useSaveStagePlan(eventId: number) {
  const client = useQueryClient();
  return useMutation({ retry: false, mutationFn: (body: Record<string, unknown>) => sendCommand<StagePlan>(base(eventId), "PUT", body),
    onSuccess: data => { client.setQueryData(stagesKey(eventId), data);
      void client.invalidateQueries({ queryKey: ["staff-event-admission", eventId] }); } });
}

export function useStageShortlist(eventId: number, stageId: number) {
  const client = useQueryClient(); const key = [...stagesKey(eventId), "shortlist", stageId];
  const path = `${base(eventId)}${stageId}/shortlist/`;
  const done = () => { void client.invalidateQueries({ queryKey: stagesKey(eventId) }); };
  const query = useQuery({ queryKey: key, retry: false, queryFn: () => staffRequest<Shortlist>(path) });
  const preview = useMutation({ retry: false, mutationFn: (selection: ShortlistSelection) =>
    staffRequest<ShortlistPlan>(`${path}preview/`, { method: "POST", body: JSON.stringify(selection) }) });
  const apply = useMutation({ retry: false, onSuccess: done, mutationFn: (body: ShortlistSelection & { fingerprint: string }) =>
    sendCommand<Shortlist>(`${path}apply/`, "POST", body) });
  const publish = useMutation({ retry: false, onSuccess: done, mutationFn: (shortlistId: number) =>
    sendCommand<Shortlist>(`${path}publish/`, "POST", { shortlist_id: shortlistId }) });
  return { query, preview, apply, publish };
}

export function useStageCommands(eventId: number, stageId: number) {
  const client = useQueryClient();
  const done = () => { void client.invalidateQueries({ queryKey: stagesKey(eventId) }); };
  const extend = useMutation({ retry: false, onSuccess: done, mutationFn: (body: { team_id: number; until: string; reason: string }) =>
    sendCommand<Extension>(`${base(eventId)}${stageId}/extensions/`, "POST", body) });
  const triage = useMutation({ retry: false, onSuccess: done, mutationFn: (body: { submission_ids: number[]; triage: string; reason: string }) =>
    sendCommand<{ updated: number }>(`${base(eventId)}${stageId}/triage/`, "POST", body) });
  return { extend, triage };
}

/** The organiser project list (up to 20 pages), used to find a stage's pending entries for bulk triage. */
export function useOrganizerProjects(eventId: number, enabled: boolean) {
  return useQuery({ queryKey: [...stagesKey(eventId), "projects"], enabled, retry: false, queryFn: async () => {
    const rows: OrganizerProject[] = [];
    for (let page = 1; page <= 20; page += 1) {
      const data = await staffRequest<Page<OrganizerProject>>(`/admin/events/${eventId}/submissions/?page=${page}`);
      rows.push(...data.results);
      if (!data.next) break;
    }
    return rows;
  } });
}

export function pendingSubmissionIds(projects: readonly OrganizerProject[], stageId: number) {
  return projects.filter(row => row.stages?.some(entry => entry.stage_id === stageId && entry.snapshot_id && entry.triage === "pending"))
    .map(row => row.id);
}
