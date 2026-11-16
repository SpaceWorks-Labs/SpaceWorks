// Server state for the event badge designer (TanStack Query). Routes are E-B1's
// (backend apps/card_designs/views_badges.py); saving is the ordinary compare-and-swap design PUT.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { CardDesign, CardDocument } from "../../../components/card-designer/cardTypes";
import { designKey } from "../../../components/card-designer/designerApi";
import { staffRequest } from "../../../lib/api";
import type { BadgeRole } from "./badgeLabels";
import type { BadgeSettings } from "./badgeNormalize";

export type BadgeRoleRow = { role: BadgeRole; design_id: number | null; format: "badge_v1" | "free_canvas" | "none"; published: boolean };
export type BadgeField = { key: string; label: string };
export type BadgeDesigns = {
  event_id: number; event_title: string; organisation_name: string; role_badges: boolean; roles: BadgeRoleRow[];
  fields: BadgeField[]; max_print_fields: number; sponsor_limit_max: number;
  presets: { id: string; width_mm: number; height_mm: number }[]; templates: string[];
  branding: { has_organisation_logo: boolean; has_event_logo: boolean; sponsor_count: number };
};
export type BadgeImportResult = { design: CardDesign; notes: string[]; unmatched_fields: string[] };

/** A design document whose front is compiled by the server from these settings. */
export type BadgeDocument = { version: 2; source: { format: "badge_v1"; settings: BadgeSettings } };

export const badgeDesignsKey = (eventId: number) => ["event-badge-designs", eventId] as const;

export function useBadgeDesigns(eventId: number) {
  return useQuery({ queryKey: badgeDesignsKey(eventId),
    queryFn: () => staffRequest<BadgeDesigns>(`/admin/events/${eventId}/badge-designs`) });
}

/** The settings stored in a design, or null when it is not (or no longer) a badge design. */
export function badgeSource(design: CardDesign): unknown {
  const source = (design.document as CardDocument & { source?: { format?: string; settings?: unknown } }).source;
  return source?.format === "badge_v1" ? source.settings ?? {} : null;
}

export function saveBadge(designId: number, settings: BadgeSettings, revision: number) {
  const document: BadgeDocument = { version: 2, source: { format: "badge_v1", settings } };
  return staffRequest<CardDesign>(`/admin/card-designs/${designId}`, { method: "PUT", body: JSON.stringify({ document, revision }) });
}

function useRefresh(eventId: number) {
  const client = useQueryClient();
  return (design?: CardDesign) => {
    if (design) client.setQueryData(designKey(design.id), design);
    void client.invalidateQueries({ queryKey: badgeDesignsKey(eventId) });
    void client.invalidateQueries({ queryKey: ["event-card-designs", eventId] });
  };
}

/** Open the role's badge (the attendee badge starts on first use; other roles start as a copy of it). */
export function useStartRoleBadge(eventId: number) {
  const refresh = useRefresh(eventId);
  return useMutation({
    mutationFn: ({ role, restart = false }: { role: BadgeRole; restart?: boolean }) =>
      staffRequest<{ design: CardDesign; created: boolean }>(`/admin/events/${eventId}/badge-designs/${role}`,
        { method: "POST", body: JSON.stringify({ restart }) }),
    onSuccess: (result) => refresh(result.design),
  });
}

export function useImportBadge(eventId: number, designId: number) {
  const refresh = useRefresh(eventId);
  return useMutation({
    mutationFn: (file: unknown) => staffRequest<BadgeImportResult>(`/admin/card-designs/${designId}/badge-import`,
      { method: "POST", body: JSON.stringify({ file }) }),
    onSuccess: (result) => refresh(result.design),
  });
}

export function useConvertBadge(eventId: number, designId: number) {
  const refresh = useRefresh(eventId);
  return useMutation({
    mutationFn: () => staffRequest<CardDesign>(`/admin/card-designs/${designId}/convert-to-free-canvas`, { method: "POST", body: "{}" }),
    onSuccess: (design) => refresh(design),
  });
}
