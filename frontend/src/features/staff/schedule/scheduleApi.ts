import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { AttentionLink } from "../panels/dashboardAreas/attention";

/** Hand-typed until the integrator regenerates the OpenAPI client (operations/views_schedule.py). */
export type ScheduleLayer = "bookings" | "events" | "machine_jobs" | "maintenance" | "shifts";
export type ScheduleEntry = { layer: ScheduleLayer; area: string; id: number; title: string; starts_at: string; ends_at: string;
  status: string; link: AttentionLink };
export type Schedule = { from: string; to: string; layers: ScheduleLayer[]; entries: ScheduleEntry[]; groups: { area: string; count: number }[] };

export const scheduleKey = (makerspaceId: number, start: string, end: string) => ["schedule", makerspaceId, start, end] as const;

/** One read per window; layer toggles filter on the client, so switching a layer costs no request. */
export function useSchedule(makerspaceId: number, start: string, end: string) {
  return useQuery({
    queryKey: scheduleKey(makerspaceId, start, end),
    queryFn: ({ signal }) => staffRequest<Schedule>(`/admin/makerspace/${makerspaceId}/schedule?${new URLSearchParams({ start, end })}`, { signal }),
  });
}

export function layerLabel(layer: string) {
  const labels: Record<string, string> = {
    bookings: t`Bookings`, events: t`Events`, shifts: t`Volunteer shifts`, machine_jobs: t`Machine jobs`,
    maintenance: t`Maintenance and outages`,
  };
  return labels[layer] ?? layer;
}

export function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: t`Awaiting approval`, confirmed: t`Confirmed`, published: t`Published`, due: t`Due`, outage: t`Out of use`,
    open: t`Open`, in_progress: t`In progress`, on_hold: t`On hold`, completed: t`Done`,
  };
  return labels[status] ?? status.replace(/_/g, " ");
}
