import { formatLocale } from "../../lib/format";
import { plural, t } from "@lingui/core/macro";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { DetailLayout } from "../../components/layouts";
import { KeyValueCard, StatusPill, type CalloutProps } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { cancelOwnServiceRequest } from "../machine-service/api";
import { ServiceCancelButton } from "../machine-service/ServiceCancelButton";
import { fetchMyJob, jobKeys } from "./api";
import { JobChangesPanel } from "./JobChangesPanel";
import { JobConsumablesReportCard } from "./JobConsumablesReportCard";
import { MemberJobWatch } from "./MemberJobWatch";
import { MemberJobMedia } from "./MemberJobMedia";
import { JobPickupCard } from "./JobPickupCard";
import { JobQueueStatus } from "./JobQueueStatus";
import { JobQuoteCard } from "./JobQuoteCard";
import { JobTimeline } from "./JobTimeline";
import { MemberJobsShell, type MemberJobsContext } from "./MemberJobsShell";
import { failureText, jobLabel, jobRefetchInterval, type MemberJob } from "./types";
import { ReportProblem } from "../repairs/ReportProblem";

const day = (iso: string) => new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString(formatLocale(), { weekday: "short", day: "numeric", month: "short" });

function outcomeBanner(job: MemberJob): CalloutProps | undefined {
  if (job.label === "failed") return { size: "banner", tone: "danger", lead: failureText(job), body: job.reason || undefined };
  if (job.label === "rejected") return { size: "banner", tone: "danger", lead: "This job wasn't approved.", body: job.reason || t`Contact the space if you have questions.` };
  if (job.label === "not_collected") return { size: "banner", tone: "warn", lead: "Not collected in time.", body: t`It wasn't picked up within 14 days, so it now belongs to the space.` };
  // A failed run that was re-queued is back in line; the member still sees what happened.
  if (job.fail_code && job.failure_outcome && !["collected", "cancelled"].includes(job.label)) return { size: "banner", tone: "warn", lead: failureText(job) };
  return undefined;
}

function JobDetail({ id, context }: { id: number; context: MemberJobsContext }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: jobKeys.detail(id), queryFn: () => fetchMyJob(id), enabled: context.ready && id > 0, retry: false,
    refetchInterval: current => jobRefetchInterval(current.state.data) });
  const job = query.data;
  const activityKey = ["member", context.slug, "activity"];
  const updated = (next: MemberJob) => {
    queryClient.setQueryData(jobKeys.detail(id), next);
    void queryClient.invalidateQueries({ queryKey: jobKeys.all });
    void queryClient.invalidateQueries({ queryKey: activityKey });
  };
  const missing = query.error instanceof StructuredApiError && [403, 404].includes(query.error.status);
  const label = job ? jobLabel(job.label) : undefined;
  return <DetailLayout back={{ label: t`My machine jobs`, href: context.path("member/machine-jobs") }}
    state={context.bootstrapError ? { status: "error", error: t`Couldn't load this makerspace. Try again.` }
      : !context.ready || query.isPending && id > 0 ? { status: "loading" } : query.isError && !missing
      ? { status: "error", error: t`Couldn't load this job. Try again.`, onRetry: () => { void query.refetch(); } } : { status: "ready" }}
    isEmpty={missing || id <= 0} empty={{ message: t`We couldn't find that job in your account.`, action: { label: t`My machine jobs`, href: context.path("member/machine-jobs") } }}
    title={job?.title ?? t`Machine job`} identity={{ kind: "icon", icon: "Wrench", tone: "info" }}
    status={label ? <StatusPill label={label.text} tone={label.tone} /> : undefined}
    meta={job ? [job.machine_type_name, plural(job.copies, { one: "# copy", other: "# copies" }), ...(job.needed_by ? [t`Needed by ${day(job.needed_by)}`] : [])] : undefined}
    banner={job ? outcomeBanner(job) : undefined}
    main={job ? <div className="grid gap-5">
      <JobPickupCard job={job} />
      <JobQuoteCard job={job} paymentsHref={context.path("member/payments")} onUpdated={updated} />
      <JobChangesPanel job={job} slug={context.slug} onUpdated={updated} />
      <JobConsumablesReportCard job={job} onUpdated={() => { void query.refetch(); }} />
      {job.label === "in_queue" || job.label === "in_progress" ? <section className="desk-panel p-5" aria-label={t`Queue and estimate`}><JobQueueStatus job={job} /></section> : null}
      {job.label === "submitted" ? <p className="text-sm text-muted">{t`Staff will review your job. You'll see a quote here if it needs one.`}</p> : null}
      <section className="desk-panel grid gap-3 p-5" aria-labelledby="job-timeline-title">
        <h2 id="job-timeline-title" className="title-panel">{t`Timeline`}</h2>
        <JobTimeline timeline={job.timeline} />
      </section>
      {job.machine_name && (context.features ?? []).includes("machines.issue_reporting") ? <div className="justify-self-start">
        <ReportProblem source={{ makerspace_id: job.makerspace_id, machine_job_id: job.id }} label={t`Report a problem with the machine`} /></div> : null}
      {job.label === "in_progress" && job.machine_name && (context.features ?? []).includes("machines.integrations.video") ? <MemberJobWatch jobId={job.id} /> : null}
      {job.machine_name && ((context.features ?? []).includes("machines.integrations.artifacts") || (context.features ?? []).includes("machines.integrations.detections"))
        ? <MemberJobMedia jobId={job.id} artifacts={(context.features ?? []).includes("machines.integrations.artifacts")} detections={(context.features ?? []).includes("machines.integrations.detections")} /> : null}
      {job.can_cancel ? <div className="justify-self-start"><ServiceCancelButton title={job.title} onCancel={() => cancelOwnServiceRequest(job.id)}
        invalidate={[jobKeys.detail(id), jobKeys.all, activityKey]} /></div> : null}
    </div> : null}
    aside={job ? <KeyValueCard items={[
      { label: t`Status`, value: label?.text ?? "" },
      { label: t`Machine type`, value: job.machine_type_name },
      ...(job.machine_name ? [{ label: t`Machine`, value: job.machine_name }] : []),
      { label: t`Requested`, value: day(job.created_at) },
      ...(job.pickup_location && job.label === "ready_to_collect" ? [{ label: t`Pickup`, value: job.pickup_location }] : []),
    ]} /> : undefined} />;
}

/** `member/machine-jobs/:jobId`: one of the member's own jobs, from request to pickup. */
export function MachineJobPage() {
  const { jobId = "" } = useParams();
  const id = /^\d+$/.test(jobId) ? Number(jobId) : 0;
  return <MemberJobsShell>{context => <JobDetail id={id} context={context} />}</MemberJobsShell>;
}
