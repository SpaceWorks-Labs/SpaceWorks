import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../../../lib/api";

/** A machine type's setup (decisions 341/343): booking defaults for new bookable spaces, training notes and where members see them. */
export type ApprovalMode = "" | "instant" | "approve";
export type TypeSetup = {
  booking_slot_minutes: number | null; booking_buffer_before_minutes: number | null; booking_buffer_after_minutes: number | null;
  booking_approval_mode: ApprovalMode; training_notes: string; notes_at_session_start: boolean; notes_at_job_request: boolean; updated_at: string | null;
};
export type TypeDocument = { id: number; title: string; original_filename: string; content_type: string; size_bytes: number; member_visible: boolean; created_at: string };
type Upload = { url: string; method?: string; headers?: Record<string, string>; fields?: Record<string, string> };

const base = (makerspaceId: number, typeId: number) => `/admin/makerspaces/${makerspaceId}/machine-types/${typeId}`;
const send = (method: string, body?: unknown) => ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
export const setupKey = (makerspaceId: number, typeId: number) => ["machine-type-setup", makerspaceId, typeId] as const;
export const typeDocsKey = (makerspaceId: number, typeId: number) => ["machine-type-documents", makerspaceId, typeId] as const;

export function useTypeSetup(makerspaceId: number, typeId: number) {
  return useQuery({ queryKey: setupKey(makerspaceId, typeId), retry: false, queryFn: () => staffRequest<TypeSetup>(`${base(makerspaceId, typeId)}/setup`) });
}

export function useSaveTypeSetup(makerspaceId: number, typeId: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: (body: Partial<TypeSetup>) => staffRequest<TypeSetup>(`${base(makerspaceId, typeId)}/setup`, send("PATCH", body)),
    onSuccess: saved => { client.setQueryData(setupKey(makerspaceId, typeId), saved); void client.invalidateQueries({ queryKey: ["member", "machine-type-guide"] }); } });
}

export function useApplyBookingDefaults(makerspaceId: number, typeId: number) {
  return useMutation({ mutationFn: () => staffRequest<{ spaces: number[] }>(`${base(makerspaceId, typeId)}/setup/apply-booking-defaults`, send("POST")) });
}

export function useTypeDocuments(makerspaceId: number, typeId: number) {
  return useQuery({ queryKey: typeDocsKey(makerspaceId, typeId), retry: false, queryFn: () => staffRequest<TypeDocument[]>(`${base(makerspaceId, typeId)}/documents`) });
}

/** Presign, send the bytes to storage, then attach the row; a refusal at any step is the error the staff member reads. */
export async function uploadTypeDocument(makerspaceId: number, typeId: number, file: File, title: string, memberVisible: boolean) {
  const root = `${base(makerspaceId, typeId)}/documents`;
  const presigned = await staffRequest<{ object_key: string; upload: Upload }>(`${root}/presign`,
    send("POST", { filename: file.name, content_type: file.type || "application/octet-stream" }));
  const { upload } = presigned;
  if (upload.method === "PUT") {
    const response = await fetch(upload.url, { method: "PUT", body: file, headers: upload.headers });
    if (!response.ok) throw new Error(t`Storage upload failed (${response.status})`);
  } else {
    const form = new FormData();
    Object.entries(upload.fields ?? {}).forEach(([key, value]) => form.append(key, value));
    form.append("file", file);
    const response = await fetch(upload.url, { method: "POST", body: form });
    if (!response.ok) throw new Error(t`Storage upload failed (${response.status})`);
  }
  return staffRequest<TypeDocument>(root, send("POST", { object_key: presigned.object_key, title, original_filename: file.name, member_visible: memberVisible }));
}

export const typeDocumentUrl = (makerspaceId: number, typeId: number, docId: number) =>
  staffRequest<{ url: string }>(`${base(makerspaceId, typeId)}/documents/${docId}`);
export const deleteTypeDocument = (makerspaceId: number, typeId: number, docId: number) =>
  staffRequest<unknown>(`${base(makerspaceId, typeId)}/documents/${docId}`, send("DELETE"));
