import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { DetailLayout, ListLayout } from "../../../components/layouts";
import { CASE_STATUS_TABS, listRefundCases, refundCaseKey, type RefundCase } from "./refundsApi";
import { RefundCaseRow } from "./RefundCaseRow";
import { RefundDecisionDialog } from "./RefundDecisionDialog";
import { RefundPolicyPanel } from "./RefundPolicyPanel";

const DECIDABLE = new Set(["open", "approval_failed"]);

/**
 * Refund cases the actor may read. The API narrows the list to their domains (or all of
 * them for finance); deciding re-checks authority per case, so `canDecide` only hides
 * buttons a finance-only reader could not use anyway.
 */
export function RefundQueue({ makerspaceId, makerspaceName, canDecide, canEditPolicy }: {
  makerspaceId: number; makerspaceName?: string; canDecide: boolean; canEditPolicy: boolean;
}) {
  const [status, setStatus] = useState<string>("open");
  const [page, setPage] = useState(1);
  const [deciding, setDeciding] = useState<RefundCase | null>(null);
  const [policyOpen, setPolicyOpen] = useState(false);
  const cases = useQuery({
    queryKey: refundCaseKey(makerspaceId, status, page),
    queryFn: () => listRefundCases(makerspaceId, status, page),
  });
  const tabs = CASE_STATUS_TABS.map(([value, label]) => ({
    key: value || "all", label, count: status === value ? cases.data?.count : undefined,
  }));
  return <ListLayout
    header={{ title: t`Refunds`, subtitle: t`What members may be owed by ${makerspaceName ?? "your makerspace"}. No money moves until someone approves it.`,
      secondary: { label: t`Refund policy`, onClick: () => setPolicyOpen(true) } }}
    state={cases.isLoading ? { status: "loading" } : cases.error && !cases.data
      ? { status: "error", error: t`Couldn't load refunds. Try again.`, onRetry: () => { void cases.refetch(); } } : { status: "ready" }}
    isEmpty={cases.data?.count === 0}
    empty={{ message: status === "open" ? t`Nothing to decide. New refund requests and cancellations that owe money appear here.` : t`No refunds in this view yet.` }}
    tabs={tabs} activeTab={status || "all"} onTabChange={(key) => { setStatus(key === "all" ? "" : key); setPage(1); }}
    pagination={{ page, count: cases.data?.count ?? 0, pageSize: 24, onChange: setPage }}
    body={{ kind: "rows", rows: (cases.data?.results ?? []).map((row) =>
      <RefundCaseRow key={row.id} row={row} onOpen={canDecide && DECIDABLE.has(row.status) ? () => setDeciding(row) : undefined} />) }}
    detail={<>
      {deciding ? <RefundDecisionDialog key={deciding.id} makerspaceId={makerspaceId} refundCase={deciding}
        onClose={() => setDeciding(null)} /> : null}
      {policyOpen ? <DetailLayout presentation="drawer" open onClose={() => setPolicyOpen(false)} title={t`Refund policy`}
        state={{ status: "ready" }} main={<RefundPolicyPanel makerspaceId={makerspaceId} canEdit={canEditPolicy} />} /> : null}
    </>}
  />;
}
