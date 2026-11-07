// Server state for one card design (TanStack Query). Saves are compare-and-swap on
// `revision`: a 409 means someone else saved, and the designer offers to reload.
import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest, staffRequestBlob } from "../../lib/api";
import type { CardDesign, CardDocument, CardFont, CardTemplate } from "./cardTypes";

const base = (id: number) => `/admin/card-designs/${id}`;
export const designKey = (id: number) => ["card-design", id] as const;

export function useCardDesignQuery(id: number) {
  return useQuery({ queryKey: designKey(id), queryFn: () => staffRequest<CardDesign>(base(id)) });
}

export function saveDesign(id: number, document: CardDocument, revision: number) {
  return staffRequest<CardDesign>(base(id), { method: "PUT", body: JSON.stringify({ document, revision }) });
}

function useDesignAction(id: number, path: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown> = {}) =>
      staffRequest<CardDesign>(`${base(id)}/${path}`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (design) => client.setQueryData(designKey(id), design),
  });
}

export const usePublishDesign = (id: number) => useDesignAction(id, "publish");
export const useSubmitDesign = (id: number) => useDesignAction(id, "submit");
export const useApproveDesign = (id: number) => useDesignAction(id, "approve");
export const useRejectDesign = (id: number) => useDesignAction(id, "reject");
export const useResetDesign = (id: number) => useDesignAction(id, "reset");

export function useTemplates(id: number, enabled = true) {
  return useQuery({ queryKey: ["card-design-templates", id], queryFn: () => staffRequest<CardTemplate[]>(`${base(id)}/templates`),
    staleTime: Infinity, enabled });
}

export function useFonts(id: number, query: string, script: string) {
  return useQuery({
    queryKey: ["card-fonts", id, query, script],
    queryFn: () => staffRequest<{ count: number; results: CardFont[] }>(
      `${base(id)}/fonts?q=${encodeURIComponent(query)}&script=${encodeURIComponent(script)}`),
    staleTime: 60_000,
  });
}

export function prepareFont(id: number, family: string) {
  return staffRequest<{ state: string }>(`${base(id)}/fonts/prepare`, { method: "POST", body: JSON.stringify({ family }) });
}

export async function previewBlob(id: number, document: CardDocument, side: "front" | "back", format: "png" | "pdf",
  longNames: boolean) {
  return staffRequestBlob(`${base(id)}/preview`, {
    method: "POST", body: JSON.stringify({ document, side, format, long_names: longNames }),
  });
}

export function exportDesign(id: number) {
  return staffRequest<Record<string, unknown>>(`${base(id)}/export`);
}

export function importDesign(id: number, file: unknown) {
  return staffRequest<{ design: CardDesign; notes: string[] }>(`${base(id)}/import`, {
    method: "POST", body: JSON.stringify({ file }),
  });
}

type Presign = { asset_id: string; url: string; fields?: Record<string, string>; method?: string;
  headers?: Record<string, string> };

/** Presign -> upload to object storage (no auth header) -> finalise (checked and re-encoded server-side). */
export async function uploadAsset(id: number, kind: "background" | "watermark" | "image", file: File) {
  const presign = await staffRequest<Presign>(`${base(id)}/assets`, {
    method: "POST", body: JSON.stringify({ kind, content_type: file.type || "application/octet-stream" }),
  });
  if (presign.method === "PUT") {
    const upload = await fetch(presign.url, { method: "PUT", body: file, headers: presign.headers });
    if (!upload.ok) throw new Error(t`Upload failed (${upload.status})`);
  } else {
    const form = new FormData();
    Object.entries(presign.fields ?? {}).forEach(([key, value]) => form.append(key, value));
    form.append("file", file);
    const upload = await fetch(presign.url, { method: "POST", body: form });
    if (!upload.ok) throw new Error(t`Upload failed (${upload.status})`);
  }
  return staffRequest<{ asset_id: string; mean_colour: string; width_px: number; height_px: number }>(
    `${base(id)}/assets/finalize`, { method: "POST", body: JSON.stringify({ asset_id: presign.asset_id }) });
}

export function assetUrlPath(id: number, assetId: string) {
  return `${base(id)}/assets/${assetId}`;
}
