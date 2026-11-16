import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../../lib/api";
import type { AddressingStyleEnum, BackupDestination, BackupDestinationUpload, DestinationProbe } from "../../../../generated/api";
import { patch, post, type Page } from "../../platformParity/parityRequest";

// Types come from the generated client (apps/backup/serializers_offsite.py via OpenAPI).
export type Addressing = AddressingStyleEnum;
// The serializer is read+write, so the spec marks writable fields optional; a read always has them.
export type Destination = BackupDestination & Required<Pick<BackupDestination,
  "endpoint_url" | "region" | "prefix" | "addressing_style" | "enabled" | "retention_days">>;
export type Upload = BackupDestinationUpload;
export type Probe = DestinationProbe;
/** Writable fields. Credentials are write-only: blank keeps the stored pair on an update. */
export type DestinationBody = Partial<Pick<Destination, "name" | "endpoint_url" | "bucket" | "region" | "prefix"
  | "addressing_style" | "enabled" | "retention_days">> & { access_key_id?: string; secret_access_key?: string };

const BASE = "/admin/platform/backup-destinations";
const listKey = ["platform-backup-destinations"] as const;

export function useDestinations(page: number) {
  return useQuery({ queryKey: [...listKey, page], queryFn: () => staffRequest<Page<Destination>>(`${BASE}?page=${page}`, {}, "platform") });
}

export function useUploads(destinationId: number, page: number) {
  return useQuery({ queryKey: [...listKey, destinationId, "uploads", page],
    queryFn: () => staffRequest<Page<Upload>>(`${BASE}/${destinationId}/uploads?page=${page}`, {}, "platform") });
}

function useInvalidating<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const client = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => client.invalidateQueries({ queryKey: listKey }) });
}

export const useSaveDestination = (id?: number) =>
  useInvalidating((body: DestinationBody) => id ? patch<Destination>(`${BASE}/${id}`, body) : post<Destination>(BASE, body));
export const useRetireDestination = () => useInvalidating((id: number) => post<Destination>(`${BASE}/${id}/retire`));
export const useProbeDestination = () => useInvalidating((id: number) => post<Probe>(`${BASE}/${id}/test`));
export const usePushNow = () => useMutation({ mutationFn: () => post<{ detail: string }>(`${BASE}/push`) });
/** Copies a verified offsite copy back over the archive's primary bytes. */
export const useRehydrate = () => useMutation({ mutationFn: ({ archiveId, destination }: { archiveId: string; destination: number }) =>
  post<{ detail: string }>(`/admin/platform/backups/${archiveId}/rehydrate`, { destination }) });
