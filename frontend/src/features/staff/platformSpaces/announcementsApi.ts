import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { post, type Page } from "./spacesApi";

export type AnnouncementSeverity = "info" | "maintenance" | "policy" | "warning";
export type Announcement = {
  id: number; title: string; body: string; severity: AnnouncementSeverity; audience: "all_spaces" | "selected_spaces";
  makerspaces: { id: number; name: string }[]; starts_at: string; ends_at: string | null; send_email: boolean;
  show_to_members: boolean; email_sent_at: string | null; email_recipient_count: number; cancelled_at: string | null;
  created_by: string | null; created_at: string; status: "scheduled" | "live" | "ended" | "cancelled";
};
export type AnnouncementBody = Pick<Announcement, "title" | "body" | "severity" | "audience" | "starts_at" | "ends_at" | "send_email" | "show_to_members"> & {
  makerspace_ids: number[];
};

export const severityLabels = (): Record<AnnouncementSeverity, string> => ({
  info: t`Information`, maintenance: t`Maintenance`, policy: t`Policy change`, warning: t`Warning`,
});

const BASE = "/admin/platform/announcements";
const key = ["platform-announcements"] as const;

export function useAnnouncements(page: number) {
  return useQuery({ queryKey: [...key, page], queryFn: () => staffRequest<Page<Announcement>>(`${BASE}?page=${page}`, {}, "platform") });
}

export function useCreateAnnouncement() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: AnnouncementBody) => post<Announcement>(BASE, body),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
}

export function useCancelAnnouncement() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => post<Announcement>(`${BASE}/${id}/cancel`),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
}
