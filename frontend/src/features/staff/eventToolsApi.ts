import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { toast } from "../../components/ui/toastStore";
import type { CustomAnswers } from "../forms/customFormTypes";
import { eligibleMemberKey, eventKeys, type EventRegistration, type StaffEvent } from "./eventsApiTypes";
import { organizedEventKeys } from "./organizedEventsApi";

function useInvalidateTools(makerspaceId: number, eventId: number) {
  const client = useQueryClient();
  return async () => Promise.all([
    client.invalidateQueries({ queryKey: eventKeys.list(makerspaceId) }),
    client.invalidateQueries({ queryKey: eventKeys.detail(eventId) }),
    client.invalidateQueries({ queryKey: eventKeys.registrations(eventId) }),
    client.invalidateQueries({ queryKey: eligibleMemberKey(eventId) }),
    client.invalidateQueries({ queryKey: ["events", "accessible"] }),
    client.invalidateQueries({ queryKey: organizedEventKeys.all }),
    client.invalidateQueries({ queryKey: ["public-events"] }),
    client.invalidateQueries({ queryKey: ["public-event"] }),
    client.invalidateQueries({ queryKey: ["member"] }),
    client.invalidateQueries({ queryKey: ["event-ticket"] }),
  ]);
}

export function useDuplicateEvent(makerspaceId: number, eventId: number) {
  const invalidate = useInvalidateTools(makerspaceId, eventId);
  return useMutation({
    mutationFn: (attachSeries: boolean) => staffRequest<StaffEvent>(`/admin/events/${eventId}/duplicate/`, {
      method: "POST", body: JSON.stringify({ attach_series: attachSeries }),
    }),
    onSuccess: async (created) => { await invalidate(); toast(`Created draft: ${created.title}`); },
  });
}

export function useEditRegistrationAnswers(makerspaceId: number, eventId: number) {
  const invalidate = useInvalidateTools(makerspaceId, eventId);
  return useMutation({
    mutationFn: ({ registrationId, answers }: { registrationId: number; answers: CustomAnswers }) =>
      staffRequest<EventRegistration>(`/admin/event-registrations/${registrationId}/answers/`, {
        method: "PATCH", body: JSON.stringify({ custom_answers: answers }),
      }),
    onSuccess: invalidate,
  });
}

export function useRestoreRegistration(makerspaceId: number, eventId: number) {
  const invalidate = useInvalidateTools(makerspaceId, eventId);
  return useMutation({
    mutationFn: (registrationId: number) => staffRequest<EventRegistration>(
      `/admin/event-registrations/${registrationId}/restore/`, { method: "POST", body: "{}" },
    ),
    onSuccess: invalidate,
  });
}

export function offerCancellationUndo(row: EventRegistration, restore: (id: number) => Promise<unknown>) {
  const duration = Math.min(300_000, Date.parse(row.restore_until ?? "") - Date.now());
  if (duration > 0) {
    toast("Registration cancelled. Undo is available for five minutes if admission still allows it.", {
      duration, undoKey: `event-registration:${row.id}`, undo: () => restore(row.id),
    });
  } else toast("Registration cancelled.");
}
