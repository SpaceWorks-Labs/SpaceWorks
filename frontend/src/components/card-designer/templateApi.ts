// Server state for the studio's templates (spec section 10): built-in rows plus this space's own, saved from a
// design, imported from a file, duplicated, exported and applied (keeping the design's data-field bindings).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import type { CardDesign, CardDocument } from "./cardTypes";
import { designKey } from "./designerApi";

export type StudioTemplate = {
  id: number | string; source: "builtin" | "space"; key: string | null; name?: string; label?: string; description?: string;
  kind: "card" | "certificate"; domain_hint?: string; stock?: string; orientation?: string; theme?: "light" | "dark";
  back_enabled?: boolean; document?: CardDocument; updated_at?: string;
};
export type TemplateFilter = { kind?: "card" | "certificate"; stock?: string };

const root = (makerspaceId: number) => `/admin/makerspaces/${makerspaceId}/card-templates`;
const listKey = (makerspaceId: number) => ["card-templates", makerspaceId] as const;
export const templateName = (item: StudioTemplate) => item.name ?? item.label ?? "";

export function useStudioTemplates(makerspaceId: number | undefined, filter: TemplateFilter, enabled = true) {
  const query = new URLSearchParams(Object.entries(filter).filter(([, value]) => value) as [string, string][]).toString();
  return useQuery({ queryKey: [...listKey(makerspaceId ?? 0), filter], enabled: enabled && makerspaceId !== undefined,
    queryFn: () => staffRequest<StudioTemplate[] | { results: StudioTemplate[] }>(`${root(makerspaceId!)}${query ? `?${query}` : ""}`)
      .then((body) => (Array.isArray(body) ? body : body.results)) });
}

/** One space template with its document (list rows carry none), for thumbnails. */
export function useTemplateDocument(pk: number | string, enabled: boolean) {
  return useQuery({ queryKey: ["card-template", pk], enabled, staleTime: 60_000,
    queryFn: () => staffRequest<StudioTemplate>(`/admin/card-templates/${pk}`) });
}

function useTemplateMutation<T, V>(makerspaceId: number, run: (variables: V) => Promise<T>) {
  const client = useQueryClient();
  return useMutation({ mutationFn: run, onSuccess: () => client.invalidateQueries({ queryKey: listKey(makerspaceId) }) });
}

export const useSaveAsTemplate = (makerspaceId: number) => useTemplateMutation(makerspaceId,
  (body: { design_id: number; name: string; description: string }) =>
    staffRequest<StudioTemplate>(root(makerspaceId), { method: "POST", body: JSON.stringify(body) }));
export const useImportTemplate = (makerspaceId: number) => useTemplateMutation(makerspaceId,
  (file: unknown) => staffRequest<StudioTemplate>(`${root(makerspaceId)}/import`, { method: "POST", body: JSON.stringify({ file }) }));
export const useDuplicateTemplate = (makerspaceId: number) => useTemplateMutation(makerspaceId,
  (pk: number | string) => staffRequest<StudioTemplate>(`/admin/card-templates/${pk}/duplicate`, { method: "POST", body: "{}" }));
export const useDeleteTemplate = (makerspaceId: number) => useTemplateMutation(makerspaceId,
  (pk: number | string) => staffRequest<void>(`/admin/card-templates/${pk}`, { method: "DELETE" }));
export const useRenameTemplate = (makerspaceId: number) => useTemplateMutation(makerspaceId,
  (body: { pk: number | string; name: string; description?: string }) => {
    const { pk, ...rest } = body;
    return staffRequest<StudioTemplate>(`/admin/card-templates/${pk}`, { method: "PATCH", body: JSON.stringify(rest) });
  });

export const exportTemplate = (pk: number | string) => staffRequest<Record<string, unknown>>(`/admin/card-templates/${pk}/export`);

export type AppliedTemplate = CardDesign & { unplaced_fields?: string[] };

export function useApplyTemplate(designId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { template: number | string; expected_revision: number; keep_fields: boolean }) =>
      staffRequest<AppliedTemplate>(`/admin/card-designs/${designId}/apply-template`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (design) => client.setQueryData(designKey(designId), design),
  });
}
