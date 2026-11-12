// The built-in certificate looks (Laurel, Ribbon, Spotlight) come from the server, so the template gallery, the
// Studio and the printed certificate share one source of truth: `GET admin/makerspaces/{id}/card-templates?kind=certificate`
// lists them and `.../card-templates/builtin/{key}/{theme}` returns one with its document.
import { useQuery } from "@tanstack/react-query";

import type { CardDocument } from "../../../components/card-designer/cardTypes";
import { staffRequest } from "../../../lib/api";

export type CertificateLook = { key: string; label: string };
type Row = { source?: string; key?: string | null; label?: string; name?: string };

export function useCertificateLooks(makerspaceId: number | undefined) {
  return useQuery({ queryKey: ["certificate-looks", makerspaceId], enabled: makerspaceId !== undefined, staleTime: Infinity,
    queryFn: async (): Promise<CertificateLook[]> => {
      const body = await staffRequest<Row[] | { results: Row[] }>(`/admin/makerspaces/${makerspaceId}/card-templates?kind=certificate`);
      const rows = Array.isArray(body) ? body : body.results;
      const seen = new Set<string>();
      return rows.filter((row) => row.source === "builtin" && row.key && !seen.has(row.key) && seen.add(row.key))
        .map((row) => ({ key: row.key as string, label: row.label ?? row.name ?? (row.key as string) }));
    } });
}

/** The document inside a built-in template response (a detail row with `document`, or the document itself). */
export function lookDocument(body: { document?: CardDocument } & Partial<CardDocument>): CardDocument {
  return (body.document ?? body) as CardDocument;
}

export async function fetchLook(makerspaceId: number, key: string, theme: "light" | "dark"): Promise<CardDocument> {
  const body = await staffRequest<{ document?: CardDocument } & Partial<CardDocument>>(
    `/admin/makerspaces/${makerspaceId}/card-templates/builtin/${encodeURIComponent(key)}/${theme}`);
  return { ...lookDocument(body), version: 3, kind: "certificate" };
}
