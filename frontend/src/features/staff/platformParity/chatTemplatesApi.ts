import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { patch, post, remove, type Page } from "./parityRequest";

export type ChatTemplate = { id: number; feature: string; event: string; text_body: string; is_active: boolean; updated_at: string };
export type ChatTemplateBody = Omit<ChatTemplate, "id" | "updated_at">;

const base = (spaceId: number) => `/admin/platform/spaces/${spaceId}/chat-templates`;
const key = (spaceId: number) => ["platform-chat-templates", spaceId] as const;

export function useChatTemplates(spaceId: number, page: number) {
  return useQuery({ queryKey: [...key(spaceId), page], queryFn: () => staffRequest<Page<ChatTemplate>>(`${base(spaceId)}?page=${page}`, {}, "platform") });
}

/** Create when `id` is null, otherwise a partial change of that row. */
export function useSaveChatTemplate(spaceId: number, id: number | null) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ChatTemplateBody) => id === null ? post<ChatTemplate>(base(spaceId), body) : patch<ChatTemplate>(`${base(spaceId)}/${id}`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: key(spaceId) }),
  });
}

export function useDeleteChatTemplate(spaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => remove(`${base(spaceId)}/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: key(spaceId) }),
  });
}
