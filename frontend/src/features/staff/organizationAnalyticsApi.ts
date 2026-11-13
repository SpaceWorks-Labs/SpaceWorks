import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import type { ReportKey } from "./panels/operationsReportsConfig";
import { periodParams, type AnalyticsPeriod } from "./panels/analyticsApi";
import { organizationReportGrains } from "./organizationReportChoices";
import type { OrganizationReportResponse } from "../../generated/api";
export type { OrganizationReportResponse, OrganizationReportRows, OrganizationReportBreakdown } from "../../generated/api";

const ORGANIZATION_ANALYTICS_PATH =
  "/api/v1/admin/organizations/{organization_id}/analytics/{report_key}";

function organizationAnalyticsPath(organizationId: number, reportKey: ReportKey) {
  return ORGANIZATION_ANALYTICS_PATH
    .replace("/api/v1", "")
    .replace("{organization_id}", String(organizationId))
    .replace("{report_key}", reportKey);
}

export const organizationAnalyticsKeys = {
  all: ["organization-analytics"] as const,
  report: (organizationId: number | null, reportKey: ReportKey) =>
    [...organizationAnalyticsKeys.all, organizationId, reportKey] as const,
};

export function useOrganizationAnalytics(
  organizationId: number | null,
  reportKey: ReportKey,
  period: AnalyticsPeriod = { start: "", end: "", grain: "day" },
) {
  return useQuery({
    queryKey: [...organizationAnalyticsKeys.report(organizationId, reportKey), period],
    queryFn: () => {
      if (organizationId === null) throw new Error(t`Select an organization first.`);
      return staffRequest<OrganizationReportResponse>(
        `${organizationAnalyticsPath(organizationId, reportKey)}?${periodParams(period, organizationReportGrains(reportKey))}`,
      );
    },
    enabled: organizationId !== null,
    retry: false,
  });
}
