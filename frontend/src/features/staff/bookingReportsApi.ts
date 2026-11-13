import { t } from "@lingui/core/macro";
import { useMutation, useQuery } from "@tanstack/react-query";

import type { BookingResourceUtilizationReport } from "../../generated/api";
import { staffRequest, staffRequestBlob } from "../../lib/api";
import type { ReportCell } from "./panels/OperationsReportsParts";
import { bookingKeys } from "./bookingsApi";

export type BookingReportKey = "booking-resource-utilization" | "booking-resource-utilization-pdf" | "booking-reservations" | "booking-answers";
export const bookingReportKeys = {
  resource: (tenant: number, resource: number) => [...bookingKeys.detail(resource), "reports", tenant] as const,
};

export function bookingReportFilters(resource: number, start: string, end: string) {
  const query = new URLSearchParams({ subject_kind: "bookable_space", subject_id: String(resource) });
  if (start) query.set("start", start);
  if (end) query.set("end", end);
  return query;
}

export function useBookingResourceReports(tenant: number, resource: number, start: string, end: string, analytics: boolean) {
  const filters = bookingReportFilters(resource, start, end);
  const base = `/admin/makerspace/${tenant}`;
  const validPeriod = !start || !end || start <= end;
  const query = useQuery({
    queryKey: [...bookingReportKeys.resource(tenant, resource), start, end],
    enabled: analytics && validPeriod,
    queryFn: async () => {
      const result = await staffRequest<BookingResourceUtilizationReport>(`${base}/analytics/booking-resource-utilization?${filters}`);
      // Registry rows are a generic OpenAPI JSON matrix. This resource's builder
      // only emits scalars; enforce that before passing cells to the report table.
      const rows: ReportCell[][] = result.rows.map((row) => row.map((cell) => {
        if (cell === null || ["string", "number", "boolean"].includes(typeof cell)) return cell as ReportCell;
        throw new Error(t`Invalid resource report cell.`);
      }));
      return { ...result, rows };
    },
  });
  const download = useMutation({
    mutationFn: ({ key, format }: { key: BookingReportKey; format: "csv" | "pdf" }) =>
      staffRequestBlob(`${base}/reports/${key}/export?${filters}&format=${format}`),
  });
  return { query, download, validPeriod };
}
