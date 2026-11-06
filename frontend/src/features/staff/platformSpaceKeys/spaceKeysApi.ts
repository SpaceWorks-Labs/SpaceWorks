import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { post } from "../platformSpaces/spacesApi";

export type KeyJob = { id: number; kind: "rotation" | "emergency_rekey" | "search_reindex"; status: "running" | "completed" | "failed";
  from_version: number | null; to_version: number; rows_done: number; rows_skipped: number; retained_versions: number[];
  error_code: string; started_at: string; updated_at: string; completed_at: string | null };
export type ArchiveJob = { action: "reencrypt" | "purge"; state: "queued" | "running" | "done" | "failed"; error_code: string; updated_at: string };
export type StaleArchive = { id: string; completed_at: string | null; size_bytes: number | null; reencryptable: boolean; job: ArchiveJob | null };
export type SpaceKeys = {
  active_dek_version: number | null; dek_versions: { version: number; status: string }[]; search_key_version: number | null;
  publishable_key_rotated_at: string | null; previous_publishable_key_valid_until: string | null;
  jobs: KeyJob[]; running: KeyJob | null; pii_encryption_enabled: boolean; rls_mode: string; stale_archives: StaleArchive[];
};
export type KeyAction = "rotate_dek" | "emergency_rekey" | "rotate_search_key" | "rotate_publishable_key";
export type CapabilityPlan = { key: string; summary: string; switched_on: boolean; counts: Record<string, number> };

const base = (spaceId: number) => `/admin/platform/spaces/${spaceId}`;
const keysKey = (spaceId: number) => ["platform-space-keys", spaceId] as const;
const plansKey = (spaceId: number) => ["platform-space-capability-purge", spaceId] as const;
const busy = (data?: SpaceKeys) => Boolean(data?.running || data?.stale_archives.some(row => row.job && ["queued", "running"].includes(row.job.state)));

/** Polls every few seconds while a key job or archive job is still going, so progress shows without a refresh. */
export function useSpaceKeys(spaceId: number) {
  return useQuery({ queryKey: keysKey(spaceId), queryFn: () => staffRequest<SpaceKeys>(`${base(spaceId)}/keys`, {}, "platform"),
    refetchInterval: query => busy(query.state.data) ? 3000 : false });
}

export function useRotateKey(spaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { action: KeyAction; confirm_slug: string }) => post<SpaceKeys>(`${base(spaceId)}/keys/rotate`, body),
    onSuccess: data => client.setQueryData(keysKey(spaceId), data),
  });
}

export function useArchiveKeyJob(spaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ archiveId, ...body }: { archiveId: string; action: "reencrypt" | "purge"; confirm_slug: string }) =>
      post<{ archive_id: string; job: ArchiveJob | null }>(`${base(spaceId)}/keys/archives/${archiveId}`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: keysKey(spaceId) }),
  });
}

export function useCapabilityPlans(spaceId: number) {
  return useQuery({ queryKey: plansKey(spaceId), queryFn: () => staffRequest<CapabilityPlan[]>(`${base(spaceId)}/capability-purge`, {}, "platform") });
}

export function usePurgeCapability(spaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { key: string; confirm: string }) =>
      post<{ key: string; counts: Record<string, number> }>(`${base(spaceId)}/capability-purge`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: plansKey(spaceId) }),
  });
}
