// The card-engine side of member cards: settings, one-card downloads and email, photo
// requests, and the design list (space default plus per-plan and per-title overrides).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest, staffRequestBlob } from "../../../../lib/api";
import type { CardDesign } from "../../../../components/card-designer/cardTypes";
import { downloadPdf } from "./api";
import type { MemberCard, MemberCardSettings } from "./types";

const space = (id: number) => `/admin/makerspaces/${id}`;
export const memberCardJobsPath = (id: number) => `${space(id)}/member-card-jobs`;

export function useMemberCardSettings(makerspaceId: number) {
  return useQuery({
    queryKey: ["member-card-settings", makerspaceId],
    queryFn: () => staffRequest<MemberCardSettings>(`${space(makerspaceId)}/member-card-settings`),
  });
}

export function useSaveMemberCardSettings(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<MemberCardSettings>) => staffRequest<MemberCardSettings>(
      `${space(makerspaceId)}/member-card-settings`, { method: "PUT", body: JSON.stringify(patch) }),
    onSuccess: (saved) => client.setQueryData(["member-card-settings", makerspaceId], saved),
  });
}

export function useDownloadCard() {
  return useMutation({
    mutationFn: async ({ card, format }: { card: MemberCard; format: "pdf" | "png" }) => {
      const blob = await staffRequestBlob(`/admin/member-cards/${card.id}/download?format=${format}&side=front`);
      downloadPdf(blob, `member-card-${card.number_display || card.card_number}.${format}`);
    },
  });
}

export function useEmailCard() {
  return useMutation({
    mutationFn: (card: MemberCard) => staffRequest<{ queued: boolean }>(`/admin/member-cards/${card.id}/email`, { method: "POST" }),
  });
}

export function useRequestPhoto(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ card, reason }: { card: MemberCard; reason: string }) =>
      staffRequest(`/admin/member-cards/${card.id}/photo-request`, { method: "POST", body: JSON.stringify({ reason }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["member-cards", makerspaceId] }),
  });
}

export function useMemberCardDesigns(makerspaceId: number) {
  return useQuery({
    queryKey: ["member-card-designs", makerspaceId],
    queryFn: () => staffRequest<CardDesign[]>(`${space(makerspaceId)}/card-designs`),
  });
}

export function useCreateCardOverride(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (target: { plan_id?: number; title_id?: number }) => staffRequest<CardDesign>(
      `${space(makerspaceId)}/card-designs`, { method: "POST", body: JSON.stringify({ domain: "member_cards", ...target }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["member-card-designs", makerspaceId] }),
  });
}
