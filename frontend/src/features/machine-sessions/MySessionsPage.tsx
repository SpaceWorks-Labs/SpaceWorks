import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { ListLayout } from "../../components/layouts";
import { ListRow, StatusPill } from "../../components/ui";
import { money } from "../payments/usePriceQuote";
import { MemberJobsShell, type MemberJobsContext } from "../machine-jobs/MemberJobsShell";
import { fetchMySessions, sessionKeys, type MemberSession } from "./api";
import { CHARGE_LABELS, duration, STOP_REASONS, when } from "./sessionFormat";

/** One line under the machine name: when, how long, why it stopped and what it cost. */
export function sessionSummary(session: MemberSession) {
  const parts = [when(session.started_at), duration(session.minutes)];
  if (session.status !== "live" && STOP_REASONS[session.stop_reason]) parts.push(STOP_REASONS[session.stop_reason]);
  if (session.amount != null && session.rate) parts.push(money(session.amount, session.rate.currency));
  return parts.join(" · ");
}

function SessionList({ context }: { context: MemberJobsContext }) {
  const sessions = useQuery({ queryKey: sessionKeys.mine(context.makerspaceId), queryFn: () => fetchMySessions(context.makerspaceId),
    enabled: context.ready && context.makerspaceId != null, retry: false,
    refetchInterval: current => (current.state.data ?? []).some(row => row.status === "live") ? 60_000 : false });
  const rows = sessions.data ?? [];
  return <ListLayout header={{ eyebrow: t`Member area`, title: t`My machine sessions`,
    subtitle: t`Time you spent on the space's machines. Scan a machine's QR to start one.` }}
    state={context.bootstrapError || sessions.isError
      ? { status: "error", error: "Couldn't load your sessions. Try again.", onRetry: () => { void sessions.refetch(); } }
      : !context.ready || sessions.isPending ? { status: "loading" } : { status: "ready" }}
    isEmpty={sessions.isSuccess && !rows.length}
    empty={{ message: t`No machine sessions yet. Scan the QR on a machine to start one.` }}
    body={{ kind: "rows", rows: <ul className="grid gap-3">{rows.map(session => {
      const charge = session.status === "live" ? { text: t`Running now`, tone: "info" as const }
        : session.status === "review" ? { text: t`Staff are checking the time`, tone: "warn" as const } : CHARGE_LABELS[session.charge_state];
      return <li key={session.id}><ListRow title={session.machine_name} meta={sessionSummary(session)}
        href={context.path(`machines/${session.machine_id}/use`)} identity={{ kind: "icon", icon: "Cog", tone: "accent" }}
        right={<StatusPill label={charge.text} tone={charge.tone} />} /></li>;
    })}</ul> }} />;
}

/** `member/machine-sessions`: the member's own sessions in this space, newest first. */
export function MySessionsPage() {
  return <MemberJobsShell>{context => <SessionList context={context} />}</MemberJobsShell>;
}
