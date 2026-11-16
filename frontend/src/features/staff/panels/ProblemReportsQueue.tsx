import { t } from "@lingui/core/macro";
import { useQueryClient } from "@tanstack/react-query";

import { ListLayout } from "../../../components/layouts";
import type { Tab } from "../../../components/ui";
import { invalidateInventoryViews } from "../queryInvalidation";
import { opsQueryState } from "../opsPresentation";
import type { ProblemReport } from "./AccountabilityTypes";
import { ProblemReportCard } from "./ProblemReportCard";
import { type Makerspace, useStaffGet } from "./shared";

export type ProblemReportsNav = { tabs?: Tab[]; activeTab?: string };

/** Open problem reports for the inventory area: listed and triaged by EDIT_INVENTORY holders. */
export function ProblemReportsQueue({ makerspace, nav = {} }: { makerspace: Makerspace; nav?: ProblemReportsNav }) {
  const queryClient = useQueryClient();
  const queue = useStaffGet<{ results: ProblemReport[]; truncated: boolean }>(["problem-reports", makerspace.id],
    `/admin/makerspace/${makerspace.id}/problem-reports`);
  const rows = queue.data?.results ?? [];
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["problem-reports", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["accountability", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["needs-fix-shelf", makerspace.id] });
    invalidateInventoryViews(queryClient, makerspace.id, makerspace.slug);
  };
  return <ListLayout header={{ title: t`Problem reports`, subtitle: t`Borrowers' reports of a broken or missing tool. Triage each one.` }}
    {...nav} state={opsQueryState(queue, "problem reports")} isEmpty={!rows.length}
    empty={{ message: t`No open problem reports.` }} stats={[{ label: t`Open problems`, value: rows.length }]}
    body={{ kind: "rows", rows: <>
      {rows.map(row => <ProblemReportCard key={row.id} row={row} makerspace={makerspace} onTriaged={refresh} />)}
      {queue.data?.truncated ? <p className="text-sm text-muted">{t`Showing the oldest open reports only.`}</p> : null}
    </> }} />;
}
