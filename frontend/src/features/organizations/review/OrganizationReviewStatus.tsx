import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";
import { Field, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "../../staff/platformSpaces/ActionDialog";
import { ReviewHistory } from "./ReviewHistory";
import { reviewStatusLabels, reviewStatusTone, useResubmitOrganization, useReviewHistory, type ReviewStatus } from "./reviewApi";
import { BoxArt } from "../../../components/BoxSpinner";

type Standing = Exclude<ReviewStatus, "approved">;
type Props = { organization: { id: number; name: string; review_status?: string; governance_actions: string[] } };

const guidance = (): Record<Standing, { title: string; next: string[] }> => ({
  pending_review: { title: t`Waiting for platform review`, next: [
    t`Your organization stays private until it is approved: no public page, space links or invitations yet.`,
    t`You can keep editing the profile in the meantime. You'll get a notice when a reviewer decides.`] },
  changes_requested: { title: t`Changes requested`, next: [
    t`A reviewer asked for changes before this organization can go live. Their note is below.`,
    t`Update the profile, then resubmit with a short note on what you changed.`] },
  declined: { title: t`Application declined`, next: [
    t`This organization was not approved and is closed. Its web address stays reserved for 30 days.`,
    t`If you think this was a mistake, contact the platform team with the reason shown below.`] },
  suspended: { title: t`Suspended by the platform`, next: [
    t`The public page is offline and the organization takes no new space links or invitations. Members keep their data.`,
    t`The platform team can reactivate it. The reason they gave is below.`] },
});

function Resubmit({ id }: { id: number }) {
  const [note, setNote] = useState("");
  const resubmit = useResubmitOrganization(id);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!resubmit.isPending) resubmit.mutate(note.trim(), { onSuccess: () => { setNote(""); toast(t`Sent for review again.`); } });
  };
  const error = actionErrorText(resubmit.error);
  return <form className="grid gap-3" onSubmit={submit} noValidate>
    <Field label={t`Note for the reviewer (optional)`} hint={t`${note.trim().length}/2000 characters`}>
      <textarea className="desk-input min-h-24" value={note} maxLength={2000} onChange={event => setNote(event.target.value)} />
    </Field>
    {error ? <p role="alert" className="rounded-control border border-danger-line bg-panel px-3 py-2 text-sm text-danger">{error}</p> : null}
    <button type="submit" className="desk-button-primary justify-self-start" disabled={resubmit.isPending}>
      {resubmit.isPending ? <><BoxArt size={16} mono />{t`Sending…`}</> : t`Resubmit for review`}</button>
  </form>;
}

/**
 * The applicant's view of an organization that is not approved (O-B5): where it stands, what that means
 * and what to do next. Profile governors also see the reviewer's notes and can resubmit after changes.
 */
export function OrganizationReviewStatus({ organization }: Props) {
  const status = organization.review_status as ReviewStatus | undefined;
  const governsProfile = organization.governance_actions.includes("manage_organization_profile");
  const history = useReviewHistory(organization.id, governsProfile && Boolean(status && status !== "approved"));
  if (!status || status === "approved" || !(status in guidance())) return null;
  const copy = guidance()[status as Standing];
  // Newest first: the reason that put the organization in its current standing.
  const latest = history.data?.find(entry => entry.action === status) ?? null;
  return <div className="grid gap-5">
    <div className="grid gap-3 rounded-xl border border-line bg-panel p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-3">
        <StatusPill label={reviewStatusLabels()[status]} tone={reviewStatusTone(status)} />
        <h3 className="title-section">{copy.title}</h3>
      </div>
      {copy.next.map(line => <p key={line} className="max-w-[65ch] text-sm text-ink">{line}</p>)}
      {latest?.reason ? <blockquote className="max-w-[65ch] whitespace-pre-wrap rounded-control bg-surface px-3 py-2 text-sm text-ink">
        <span className="sr-only">{t`Reviewer's note:`} </span>{latest.reason}</blockquote> : null}
      {status === "changes_requested" && governsProfile ? <Resubmit id={organization.id} /> : null}
      {!governsProfile ? <p className="text-sm text-muted">{t`An organization admin with profile rights can see the reviewer's notes and resubmit.`}</p> : null}
    </div>
    {governsProfile ? <ReviewHistory organizationId={organization.id} headingId={`org-review-history-${organization.id}`} /> : null}
  </div>;
}
