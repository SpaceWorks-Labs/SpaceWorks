import { useQuery } from "@tanstack/react-query";

import { staffRequest, StructuredApiError } from "../../../lib/api";
import type { Incident, Page } from "../../incidents/api";

/** Records an incident can point at, and the register filter that selects them (batch 1, EB9/MC11/IN6). */
export type IncidentSubject = "machine" | "event" | "booking" | "room" | "loan" | "product" | "person";

/**
 * Incidents linked to one record, through the register's own area-narrowed list. The server
 * applies the subject filter; rows carrying the subject's own column are re-checked here, so a
 * server that ignored the filter could never present the whole register as "linked to this
 * machine". `product` (through the loan) and `person` (`involved_user`) are the server's to match.
 *
 * `hidden` is true when the register is off (404) or the viewer reads no incident area (403):
 * the caller drops the section rather than showing an error for something they never had.
 */
export function useSubjectIncidents(makerspaceId: number, subject: IncidentSubject, id: number | null | undefined, enabled = true) {
  const query = useQuery({
    queryKey: ["incidents", "subject", makerspaceId, subject, id],
    enabled: enabled && Boolean(id),
    retry: false,
    queryFn: ({ signal }) => staffRequest<Page<Incident>>(
      `/admin/makerspaces/${makerspaceId}/incidents?${new URLSearchParams({ [subject]: String(id), page: "1" })}`, { signal }),
  });
  const status = query.error instanceof StructuredApiError ? query.error.status : undefined;
  const raw = query.data?.results ?? [];
  const column = subject === "person" ? "involved_user" : subject;
  const rows = raw.filter(row => {
    const value = (row as Record<string, unknown>)[column];
    return value === undefined || Number(value) === id;
  });
  const exact = rows.length === raw.length;
  return {
    query,
    hidden: status === 403 || status === 404,
    rows,
    /** Server count when every row matched; the matched rows otherwise; null while loading. */
    count: query.isLoading ? null : !query.data ? undefined : exact ? query.data.count : rows.length,
    open: rows.filter(row => row.status !== "resolved" && row.status !== "closed").length,
  };
}
