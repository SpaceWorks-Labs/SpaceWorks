import { t } from "@lingui/core/macro";
import { useState } from "react";

import { DetailLayout } from "../../../components/layouts";
import { StatusPill, type Action } from "../../../components/ui";
import { opsQueryState } from "../opsPresentation";
import { useTechnicians } from "../technicians/techniciansApi";
import { DispatchDialog } from "./DispatchDialog";
import { IssueRecord } from "./IssueRecord";
import { ServiceStateDialog } from "./ServiceStateDialog";
import { StepDialog } from "./StepDialog";
import { stepSpecs } from "./issueSteps";
import { AREA_LABELS, OPEN_STATES, STATE_LABELS, stateTone, useIssue, useIssueStep, type IssueDetail as Issue } from "./repairsApi";
import { useSubjectOptions } from "./subjectsApi";

/** One issue: what was reported, who works it, every step so far, and the next step for this viewer. */
export function IssueDetail({ id, makerspaceId, onBack }: { id: number; makerspaceId: number; onBack: () => void }) {
  const query = useIssue(id);
  const issue = query.data;
  const manager = issue?.viewer_role === "manager";
  const technicians = useTechnicians(makerspaceId, manager).data ?? [];
  const items = useSubjectOptions(makerspaceId, "inventory_product", manager).options;
  const step = useIssueStep(id);
  const [open, setOpen] = useState<string | null>(null);
  const specs = issue ? stepSpecs(issue, technicians, manager ? items : []) : {};
  const spec = open ? specs[open] : undefined;
  const actions = issue ? nextSteps(issue, manager, key => setOpen(key), () => step.mutate({ step: "start" }),
    () => step.mutate({ step: "assign", body: { myself: true } }), step.isPending) : { primary: undefined, overflow: [] };
  return <DetailLayout title={issue?.title ?? t`Issue`} back={{ label: manager ? t`All repairs` : t`My jobs`, onClick: onBack }}
    identity={{ kind: "icon", icon: "HardHat", tone: "accent" }} state={opsQueryState(query, "this issue")}
    status={issue ? <><StatusPill tone={stateTone(issue.state)} label={STATE_LABELS[issue.state]} />
      {issue.quote_state !== "none" ? <StatusPill tone={issue.quote_state === "approved" ? "success" : issue.quote_state === "declined" ? "danger" : "warn"}
        label={issue.quote_state === "pending" ? t`Quote awaiting approval` : issue.quote_state === "approved" ? t`Quote approved` : t`Quote declined`} /> : null}</> : undefined}
    meta={issue ? [`${AREA_LABELS[issue.area]}: ${issue.subject_label}`, issue.reporter_name ? t`Reported by ${issue.reporter_name}` : t`Opened by staff`] : undefined}
    actions={actions}
    main={issue ? <div className="grid gap-6">
      {step.error ? <p role="alert" className="text-sm text-danger">{step.error.message}</p> : null}
      <IssueRecord issue={issue} />
      {spec ? <StepDialog title={spec.title} submitLabel={spec.submit} fields={spec.fields} note={spec.note} makerspaceId={makerspaceId}
        pending={step.isPending} error={step.error?.message} onClose={() => setOpen(null)}
        onSubmit={body => step.mutate({ step: spec.step, body: spec.map ? spec.map(body) : body }, { onSuccess: () => setOpen(null) })} /> : null}
      {open === "dispatch" ? <DispatchDialog issue={issue} technicians={technicians} onClose={() => setOpen(null)} /> : null}
      {open === "service" ? <ServiceStateDialog issue={issue} makerspaceId={makerspaceId} onClose={() => setOpen(null)} /> : null}
    </div> : null} />;
}

function nextSteps(issue: Issue, manager: boolean, open: (key: string) => void, start: () => void, self: () => void, pending: boolean) {
  const live = OPEN_STATES.includes(issue.state);
  const working = ["triaged", "assigned", "in_progress"].includes(issue.state);
  const item = (key: string, label: string, extra: Partial<Action> = {}): Action => ({ label, onClick: () => open(key), ...extra });
  let primary: Action | undefined;
  if (manager && issue.state === "reported") primary = item("triage", "Triage");
  else if (issue.state === "triaged" || issue.state === "assigned") primary = { label: t`Start work`, onClick: start, pending };
  else if (issue.state === "in_progress") primary = item("fix", "Mark fixed", { icon: "Check" });
  else if (manager && issue.state === "fixed") primary = item("close", "Close");
  const overflow: Action[] = [];
  if (manager && working) overflow.push(item("dispatch", "Send to technicians", { icon: "Send" }), { label: t`Assign to me`, onClick: self });
  if (working) overflow.push(item("visit", "Log a visit"), item("remark", "Add a remark"), item("used", "Part used"),
    item("needed", "Part needed"), item("quote", "Record a quote"));
  if (manager && issue.quote_state === "pending") overflow.push(item("approve", "Approve quote"), item("decline", "Decline quote"));
  if (manager && issue.quote_state === "approved" && !issue.payout_entry_id) overflow.push(item("payout", "Record payout"));
  if (manager && issue.state === "reported") overflow.push(item("fix", "Fix it myself"));
  if (live) overflow.push(item("service", "In or out of service", { icon: "CircleSlash" }));
  if (manager && live) overflow.push(item("reject", "Reject", { tone: "danger" }));
  return { primary, overflow };
}
