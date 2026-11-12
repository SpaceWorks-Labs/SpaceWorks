import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { memberRequest } from "../../../lib/api";
import type { SelfReportedAchievement } from "../accountProfileTypes";
import { ownProfileKey } from "./profileEditApi";

const ROOT = "/member/profile";
export const achievementsKey = ["member", "profile", "achievements"] as const;
export const importableKey = ["member", "profile", "project-import"] as const;

export type AchievementDraft = Omit<SelfReportedAchievement, "id">;
export type ImportableSubmission = {
  id: number; title: string; event_title: string; space_name: string; submitted_at: string; already_imported: boolean;
};

/** Self-reported achievements only; verified ones come from the profile payload and are read-only. */
export function useAchievements() {
  return useQuery({ queryKey: achievementsKey, queryFn: () => memberRequest<SelfReportedAchievement[]>(`${ROOT}/achievements`), retry: false });
}

export function useAchievementMutations() {
  const client = useQueryClient();
  const refresh = () => Promise.all([client.invalidateQueries({ queryKey: achievementsKey }), client.invalidateQueries({ queryKey: ownProfileKey })]);
  const save = useMutation({
    mutationFn: ({ id, draft }: { id?: number; draft: AchievementDraft }) => memberRequest<SelfReportedAchievement>(
      id ? `${ROOT}/achievements/${id}` : `${ROOT}/achievements`, { method: id ? "PATCH" : "POST", body: JSON.stringify(draft) }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: number) => memberRequest<void>(`${ROOT}/achievements/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });
  return { save, remove };
}

/** The caller's own hackathon submissions that can become profile projects. */
export function useImportableSubmissions(enabled: boolean) {
  return useQuery({ queryKey: importableKey, enabled, queryFn: () => memberRequest<ImportableSubmission[]>(`${ROOT}/project-import`), retry: false });
}

/** 201 {id,title}; 409 already_imported, 404 not yours / not importable, 400 project cap. */
export function useImportSubmission() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (submissionId: number) => memberRequest<{ id: number; title: string }>(`${ROOT}/project-import`, { method: "POST", body: JSON.stringify({ submission_id: submissionId }) }),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: importableKey }), client.invalidateQueries({ queryKey: ownProfileKey })]),
  });
}
