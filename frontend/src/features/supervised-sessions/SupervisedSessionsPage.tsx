import { t } from "@lingui/core/macro";
import { useParams, useSearchParams } from "react-router-dom";

import { DetailLayout } from "../../components/layouts";
import { MemberJobsShell, type MemberJobsContext } from "../machine-jobs/MemberJobsShell";
import { SupervisedWorkspace } from "./SupervisedWorkspace";

const FEATURE = "machines.supervised_sessions";

function Supervised({ context, machineId, sessionId }: { context: MemberJobsContext; machineId?: number; sessionId: number | null }) {
  const on = (context.features ?? []).includes(FEATURE);
  return <DetailLayout title={machineId ? t`Supervise machine #${machineId}` : t`Supervised sessions`}
    back={{ label: t`Member area`, href: context.path("member") }} identity={{ kind: "icon", icon: "HardHat", tone: "accent" }}
    meta={[t`Lead a workshop: add the people you supervise and record each use of the machine.`]}
    state={context.bootstrapError ? { status: "error", error: t`Couldn't load this makerspace. Try again.` }
      : !context.ready ? { status: "loading" } : { status: "ready" }}
    isEmpty={!on || context.makerspaceId == null}
    empty={{ message: t`Supervised sessions aren't offered here. Ask staff if you think they should be.`, action: { label: t`Member area`, href: context.path("member") } }}
    main={on && context.makerspaceId != null
      ? <SupervisedWorkspace makerspaceId={context.makerspaceId} machineId={machineId} initialSessionId={sessionId} /> : null} />;
}

/** `member/supervised-sessions` (the instructor's sessions, `?session=` opens one) and
 *  `machines/:machineId/supervise` (start one on that machine). Member routes; staff use the drawer. */
export function SupervisedSessionsPage() {
  const { machineId = "" } = useParams();
  const [params] = useSearchParams();
  const machine = /^\d+$/.test(machineId) ? Number(machineId) : undefined;
  const session = Number(params.get("session")) || null;
  return <MemberJobsShell>{context => <Supervised context={context} machineId={machine} sessionId={session} />}</MemberJobsShell>;
}
