import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { Page } from "./parityRequest";

export type ChatTemplate = { id: number; feature: string; event: string; text_body: string; is_active: boolean; updated_at: string };
export type ChatTemplateBody = Omit<ChatTemplate, "id" | "updated_at">;
/** "platform": the superadmin console path; "space": a Space Manager's own space (#190 follow-up). */
export type ChatTemplateSurface = "platform" | "space";

const base = (spaceId: number, surface: ChatTemplateSurface) => surface === "platform"
  ? `/admin/platform/spaces/${spaceId}/chat-templates` : `/admin/makerspace/${spaceId}/chat-templates`;
const key = (spaceId: number, surface: ChatTemplateSurface) => ["chat-templates", surface, spaceId] as const;
function send<T>(surface: ChatTemplateSurface, path: string, init: RequestInit) {
  return surface === "platform" ? staffRequest<T>(path, init, "platform") : staffRequest<T>(path, init);
}

export function useChatTemplates(spaceId: number, page: number, surface: ChatTemplateSurface = "platform") {
  return useQuery({ queryKey: [...key(spaceId, surface), page],
    queryFn: () => send<Page<ChatTemplate>>(surface, `${base(spaceId, surface)}?page=${page}`, {}) });
}

/** Create when `id` is null, otherwise a partial change of that row. */
export function useSaveChatTemplate(spaceId: number, id: number | null, surface: ChatTemplateSurface = "platform") {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ChatTemplateBody) => id === null
      ? send<ChatTemplate>(surface, base(spaceId, surface), { method: "POST", body: JSON.stringify(body) })
      : send<ChatTemplate>(surface, `${base(spaceId, surface)}/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: key(spaceId, surface) }),
  });
}

export function useDeleteChatTemplate(spaceId: number, surface: ChatTemplateSurface = "platform") {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => send<void>(surface, `${base(spaceId, surface)}/${id}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: key(spaceId, surface) }),
  });
}
