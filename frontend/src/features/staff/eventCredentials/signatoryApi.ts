import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest, staffRequest, staffRequestBlob } from "../../../lib/api";

export type Signatory = { id: number; slot: 1 | 2 | 3; name: string; title: string; member_id: number | null;
  member_name: string | null; signature_artwork_id: number | null; version: number };
export type DesignApproval = { template_revision_id: number; certificate_kind: string; released: boolean;
  slots: { slot: number; signatory_id: number | null; approved: boolean }[] };
export type SignatoryState = { approval_required: boolean; signatories: Signatory[]; designs: DesignApproval[] };
export type SignatoryInput = { slot: number; name: string; title: string; member_id: number | null; signature_artwork_id: number | null };
export type PendingApproval = { signatory_id: number; slot: number; event_id: number; event_title: string;
  template_revision_id: number; certificate_kind: string; approved: boolean; name: string; title: string };

const base = (eventId: number) => `/admin/events/${eventId}/certificates/signatories/`;
export const signatoryKey = (eventId: number) => ["events", "credentials", eventId, "signatories"] as const;

export function useSignatories(eventId: number) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: signatoryKey(eventId), queryFn: () => staffRequest<SignatoryState>(base(eventId)) });
  const settle = (state: SignatoryState) => client.setQueryData(signatoryKey(eventId), state);
  const save = useMutation({ mutationFn: (input: SignatoryInput) => staffRequest<SignatoryState>(base(eventId), { method: "POST", body: JSON.stringify(input) }), onSuccess: settle });
  const remove = useMutation({ mutationFn: (slot: number) => staffRequest<SignatoryState>(`${base(eventId)}${slot}/`, { method: "DELETE" }), onSuccess: settle });
  const policy = useMutation({ mutationFn: (required: boolean) => staffRequest<SignatoryState>(`${base(eventId)}approval-policy/`,
    { method: "POST", body: JSON.stringify({ required }) }), onSuccess: settle });
  return { query, save, remove, policy };
}

export function useSignatoryCandidates(eventId: number, term: string) {
  return useQuery({ queryKey: ["events", "credentials", eventId, "signatory-candidates", term], enabled: term.trim().length >= 2,
    queryFn: () => staffRequest<{ id: number; name: string }[]>(`${base(eventId)}candidates/?${new URLSearchParams({ q: term.trim() })}`) });
}

/** Upload a signature image (PNG, JPEG or WebP, up to 2 MB); the server re-encodes and keeps it private. */
export function useUploadSignature(eventId: number) {
  return useMutation({ mutationFn: async (file: File) => {
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size < 1 || file.size > 2 * 1024 * 1024) {
      throw new Error(t`Choose a PNG, JPEG or WebP signature up to 2 MB.`);
    }
    const upload = await staffRequest<{ id: number; upload_url: string; headers: Record<string, string> }>(
      `/admin/events/${eventId}/certificate-artwork/`, { method: "POST",
        body: JSON.stringify({ content_type: file.type, content_length: file.size, purpose: "signature" }) });
    const response = await fetch(upload.upload_url, { method: "PUT", headers: upload.headers, body: file });
    if (!response.ok) throw new Error(t`The signature upload failed. Choose the image to try again.`);
    return staffRequest<{ id: number }>(`/admin/events/${eventId}/certificate-artwork/${upload.id}/finalize/`, { method: "POST", body: JSON.stringify({}) });
  } });
}

export const signatureImage = (eventId: number, artworkId: number) =>
  staffRequestBlob(`/admin/events/${eventId}/certificate-artwork/${artworkId}/`);

const approvals = (makerspaceId: number) => `/member/makerspaces/${makerspaceId}/certificate-approvals/`;
export function usePendingApprovals(makerspaceId: number) {
  const client = useQueryClient();
  const key = ["member", makerspaceId, "certificate-approvals"];
  const query = useQuery({ queryKey: key, queryFn: () => memberRequest<PendingApproval[]>(approvals(makerspaceId)), retry: false });
  const approve = useMutation({ mutationFn: (row: PendingApproval) => memberRequest(`${approvals(makerspaceId)}${row.signatory_id}/approve/`,
    { method: "POST", body: JSON.stringify({ template_revision_id: row.template_revision_id }) }),
  onSuccess: () => client.invalidateQueries({ queryKey: key }) });
  return { query, approve };
}

export const approvalPreviewPath = (makerspaceId: number, row: PendingApproval) =>
  `${approvals(makerspaceId)}${row.signatory_id}/designs/${row.template_revision_id}/preview.pdf`;
