import { useQuery } from "@tanstack/react-query";

import { ListLayout } from "../../components/layouts";
import { ListRow, StatusPill } from "../../components/ui";
import { minutesLabel } from "../machine-service/ServiceRequestEta";
import { fetchMyJobs, jobKeys } from "./api";
import { MemberJobsShell, type MemberJobsContext } from "./MemberJobsShell";
import { etaWhen, FINISHED_LABELS, jobLabel, type MemberJob } from "./types";

/** One line under the title: where the job stands in words, server values only. */
export function jobSummary(job: MemberJob, now = new Date()) {
  const parts = [job.machine_type_name];
  if (job.label === "in_queue" && job.position != null) parts.push(job.position <= 1 ? "You're next" : `#${job.position} in queue`);
  if ((job.label === "in_queue" || job.label === "in_progress") && job.eta?.estimated_finish_at && job.eta.confidence !== "unavailable") {
    parts.push(`ready ${etaWhen(job.eta.estimated_finish_at, now, minutesLabel)}`);
  }
  if (job.label === "needs_changes") parts.push("Staff need something from you");
  if (job.label === "quote_sent") parts.push("Quote waiting for your answer");
  if (job.label === "ready_to_collect" && job.pickup_location) parts.push(`Pick up at ${job.pickup_location}`);
  return parts.join(" · ");
}

function JobList({ context }: { context: MemberJobsContext }) {
  const jobs = useQuery({ queryKey: jobKeys.mine(context.makerspaceId), queryFn: () => fetchMyJobs(context.makerspaceId),
    enabled: context.ready && context.makerspaceId != null, retry: false,
    refetchInterval: current => (current.state.data ?? []).some(job => !FINISHED_LABELS.has(job.label)) ? 90_000 : false });
  const rows = jobs.data ?? [];
  // Jobs that need the member float to the top; the server already orders newest first.
  const needsYou = (job: MemberJob) => ["needs_changes", "quote_sent", "awaiting_payment", "ready_to_collect"].includes(job.label) ? 0 : 1;
  const ordered = [...rows].sort((a, b) => needsYou(a) - needsYou(b));
  return <ListLayout header={{ eyebrow: "Member area", title: "My machine jobs", subtitle: "Everything you've asked the space to make.",
    primary: { label: "Request a job", href: context.path("machine-jobs/new") } }}
    state={context.bootstrapError || jobs.isError
      ? { status: "error", error: "Couldn't load your jobs. Try again.", onRetry: () => { void jobs.refetch(); } }
      : !context.ready || jobs.isPending ? { status: "loading" } : { status: "ready" }}
    isEmpty={jobs.isSuccess && !rows.length}
    empty={{ message: "No machine jobs yet. Send the space a file and it will show up here.", action: { label: "Request a job", href: context.path("machine-jobs/new") } }}
    body={{ kind: "rows", rows: <ul className="grid gap-3">{ordered.map(job => {
      const label = jobLabel(job.label);
      return <li key={job.id}><ListRow title={job.title} href={context.path(`member/machine-jobs/${job.id}`)}
        identity={{ kind: "icon", icon: "Wrench", tone: "info" }} meta={jobSummary(job)}
        right={<StatusPill label={label.text} tone={label.tone} />} /></li>;
    })}</ul> }} />;
}

/** `member/machine-jobs`: the member's own jobs in this space, newest first. */
export function MyMachineJobsPage() {
  return <MemberJobsShell>{context => <JobList context={context} />}</MemberJobsShell>;
}
