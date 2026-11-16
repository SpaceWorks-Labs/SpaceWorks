import { t } from "@lingui/core/macro";
import { useState } from "react";
import { DetailDrawer, KeyValueCard, RelativeTime, StatusPill } from "../../../components/ui";
import { safePublicLink } from "../../publicPages/PublicCollectionCards";
import { ReviewDecisionDialog, decisionLabels } from "./ReviewDecisionDialog";
import { ReviewHistory } from "./ReviewHistory";
import { DECISIONS_BY_STATUS, reviewStatusLabels, reviewStatusTone, type ReviewDecision, type ReviewQueueRow } from "./reviewApi";

const buttonClass = (decision: ReviewDecision) => decision === "approve" || decision === "reactivate" ? "desk-button-primary"
  : decision === "decline" || decision === "suspend" ? "desk-button-danger-outline" : "desk-button";

/** One organization in the review queue: what the applicant sent, the trail so far, and the decisions open to it. */
export function OrganizationReviewDrawer({ row, onClose }: { row: ReviewQueueRow; onClose: () => void }) {
  const [decision, setDecision] = useState<ReviewDecision | null>(null);
  const decisions = DECISIONS_BY_STATUS[row.review_status] ?? [];
  const website = safePublicLink(row.website);
  return <DetailDrawer open title={row.name} onClose={onClose}>
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill label={reviewStatusLabels()[row.review_status] ?? row.review_status} tone={reviewStatusTone(row.review_status)} />
        {decisions.map(item => <button key={item} type="button" className={buttonClass(item)} onClick={() => setDecision(item)}>
          {t`${decisionLabels()[item]}…`}</button>)}
      </div>
      <KeyValueCard title={t`Application`} items={[
        { label: t`Web address`, value: `/o/${row.slug}` },
        { label: t`Submitted by`, value: row.submitted_by || t`Unknown account` },
        { label: t`Created`, value: <RelativeTime date={row.created_at} exact /> },
        ...(website ? [{ label: t`Website`, value: <a className="text-brand-ink underline" href={website} target="_blank" rel="noopener noreferrer">{row.website}</a> }] : []),
      ]} />
      <section aria-labelledby={`review-about-${row.id}`} className="grid gap-2">
        <h3 id={`review-about-${row.id}`} className="title-panel">{t`About the organization`}</h3>
        <p className="whitespace-pre-wrap text-sm text-ink">{row.description || t`No description given.`}</p>
      </section>
      <ReviewHistory organizationId={row.id} context="platform" headingId={`review-history-${row.id}`} />
    </div>
    {decision ? <ReviewDecisionDialog row={row} decision={decision} onClose={() => setDecision(null)} onDone={onClose} /> : null}
  </DetailDrawer>;
}
