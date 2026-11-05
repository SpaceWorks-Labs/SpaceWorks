// Organisation ID programmes hosted by a space (capability `membership.id_programmes`).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest, staffRequestBlob } from "../../../lib/api";
import type { CardDesign } from "../../../components/card-designer/cardTypes";

export type ProgrammeStatus = "draft" | "active" | "closed";
export type Question = { key: string; label: string; type: "text" | "choice" | "email" | "phone"; required: boolean;
  options?: string[]; placement: "front" | "back" | "hidden"; saved_details_key?: string };

export type Programme = {
  id: number; organization: number; organization_slug: string; makerspace: number; name: string; slug: string; description: string;
  status: ProgrammeStatus; registration_open: boolean; requires_approval: boolean; id_prefix: string; next_sequence: number;
  validity_mode: "none" | "fixed_date" | "days"; valid_until: string | null; validity_days: number | null;
  photo_mode: "none" | "optional" | "required"; form_schema: Question[]; public_verify: boolean; email_daily_cap: number;
  counts: { all: number; pending: number; approved: number; rejected: number; revoked: number }; can_manage: boolean;
  created_at: string; updated_at: string;
};

export type ProgrammeCardStatus = "pending" | "approved" | "rejected" | "revoked";
export type ProgrammeCard = {
  id: number; programme: number; name: string; email: string; answers: Record<string, string>; status: ProgrammeCardStatus;
  status_reason: string; source: "form" | "import" | "manual"; id_number: string; issued_at: string | null;
  expires_at: string | null; revoked_at: string | null; last_emailed_at: string | null; linked: boolean; photo_set: boolean;
  created_at: string;
};

export type ImportPreview = { headers: string[]; rows: string[][]; mapping: Record<string, number | null>; rows_total: number;
  to_create: number; skipped: { row: number; reason: string }[]; source?: "google_sheet"; sheet_sha256?: string };
/** Pasted/uploaded CSV text, or a public Google Sheet link (`membership.id_programmes_import_sheets`, L13). */
export type ImportInput = { content: string } | { source: "google_sheet"; url: string; sheet_sha256?: string };

const keys = {
  list: (organizationId: number) => ["id-programmes", organizationId] as const,
  one: (id: number) => ["id-programme", id] as const,
  cards: (id: number, status: string, search: string, page: number) => ["id-programme-cards", id, status, search, page] as const,
};
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });
export const programmeJobsPath = (id: number) => `/admin/id-programmes/${id}/card-jobs`;

export function useProgrammes(organizationId: number | null) {
  return useQuery({ queryKey: keys.list(organizationId ?? 0), enabled: organizationId !== null,
    queryFn: () => staffRequest<Programme[]>(`/admin/organizations/${organizationId}/id-programmes`) });
}

export function useCreateProgramme(organizationId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { makerspace_id: number; name: string; preset: string }) =>
      staffRequest<Programme>(`/admin/organizations/${organizationId}/id-programmes`, json("POST", input)),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.list(organizationId) }),
  });
}

export function useProgramme(id: number) {
  return useQuery({ queryKey: keys.one(id), queryFn: () => staffRequest<Programme>(`/admin/id-programmes/${id}`) });
}

export function useUpdateProgramme(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<Programme>) => staffRequest<Programme>(`/admin/id-programmes/${id}`, json("PATCH", patch)),
    onSuccess: (saved) => { client.setQueryData(keys.one(id), saved); void client.invalidateQueries({ queryKey: ["id-programmes"] }); },
  });
}

export function useProgrammeDesign(id: number) {
  return useQuery({ queryKey: ["id-programme-design", id], queryFn: () => staffRequest<CardDesign>(`/admin/id-programmes/${id}/design`) });
}

export function useProgrammeCards(id: number, status: string, search: string, page: number) {
  const params = new URLSearchParams({ page: String(page), ...(status ? { status } : {}), ...(search ? { search } : {}) });
  return useQuery({ queryKey: keys.cards(id, status, search, page),
    queryFn: () => staffRequest<{ count: number; results: ProgrammeCard[] }>(`/admin/id-programmes/${id}/cards?${params}`) });
}

function useInvalidateCards(id: number) {
  const client = useQueryClient();
  return () => Promise.all([client.invalidateQueries({ queryKey: ["id-programme-cards", id] }),
    client.invalidateQueries({ queryKey: keys.one(id) })]);
}

export function useAddProgrammeCard(id: number) {
  const refresh = useInvalidateCards(id);
  return useMutation({ mutationFn: (input: { name: string; email: string }) =>
    staffRequest<ProgrammeCard>(`/admin/id-programmes/${id}/cards`, json("POST", input)), onSuccess: refresh });
}

export function useDecide(id: number) {
  const refresh = useInvalidateCards(id);
  return useMutation({ mutationFn: (input: { action: string; ids: number[]; reason?: string }) =>
    staffRequest<{ changed: number }>(`/admin/id-programmes/${id}/cards/decide`, json("POST", input)), onSuccess: refresh });
}

export function useImportPreview(id: number) {
  return useMutation({ mutationFn: (input: ImportInput) =>
    staffRequest<ImportPreview>(`/admin/id-programmes/${id}/imports/preview`, json("POST", input)) });
}

export function useImportCommit(id: number) {
  const refresh = useInvalidateCards(id);
  return useMutation({
    mutationFn: (input: ImportInput & { mapping: Record<string, number | null>; approve: boolean }) =>
      staffRequest<{ created: number; skipped: { row: number; reason: string }[] }>(`/admin/id-programmes/${id}/imports`, json("POST", input)),
    onSuccess: refresh,
  });
}

export async function downloadProgrammeCard(card: ProgrammeCard, format: "pdf" | "png") {
  const blob = await staffRequestBlob(`/admin/id-programme-cards/${card.id}/download?format=${format}`);
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement("a"), { href: url, download: `${card.id_number || "card"}.${format}` }).click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** The programme level of the design-approval switch (#136): true, false, or null to follow the organisation/space. */
export function useProgrammeApproval(id: number) {
  const client = useQueryClient();
  const key = ["id-programme-approval", id];
  const path = `/admin/id-programmes/${id}/approval`;
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<{ required: boolean | null; inherited: boolean }>(path) });
  const save = useMutation({
    mutationFn: (required: boolean | null) => staffRequest<{ required: boolean | null; inherited: boolean }>(path, json("PUT", { required })),
    onSuccess: (value) => { client.setQueryData(key, value); void client.invalidateQueries({ queryKey: ["card-design"] }); },
  });
  return { query, save };
}
