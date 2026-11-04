import { useState } from "react";

import { ListLayout } from "../../../components/layouts";
import { ListRow, StatusPill } from "../../../components/ui";
import type { Makerspace } from "../panels/shared";
import { opsQueryState } from "../opsPresentation";
import { OpenIssueDialog } from "./OpenIssueDialog";
import { AREA_LABELS, STATE_LABELS, stateTone, useIssues, useMyJobs, type Issue } from "./repairsApi";

const FILTERS = [
  { key: "open", label: "Open", query: "state=reported,triaged,assigned,in_progress" },
  { key: "reported", label: "New reports", query: "state=reported" },
  { key: "done", label: "Fixed and closed", query: "state=fixed,closed,rejected" },
];

/** The repairs queue (managers) or "My jobs" (a Technician's assigned jobs), 24 per page. */
export function IssueQueue({ makerspace, mine, canOpen, onOpen }: {
  makerspace: Makerspace; mine: boolean; canOpen: boolean; onOpen: (id: number) => void;
}) {
  const [filter, setFilter] = useState(FILTERS[0]);
  const [page, setPage] = useState(1);
  const [opening, setOpening] = useState(false);
  const queue = useIssues(makerspace.id, `${filter.query}&page=${page}`, !mine);
  const own = useMyJobs(makerspace.id, page, mine);
  const query = mine ? own : queue;
  const rows = query.data?.results ?? [];
  return <>
    <ListLayout header={{ title: mine ? "My jobs" : "Repairs", subtitle: mine
      ? "Repair jobs assigned to you. Open one to log visits, parts and the fix."
      : "Problems members reported and repair jobs staff opened, from report to fix.",
      primary: canOpen && !mine ? { label: "New repair job", icon: "Plus", onClick: () => setOpening(true) } : undefined }}
      tabs={mine ? undefined : FILTERS.map(row => ({ key: row.key, label: row.label }))} activeTab={filter.key}
      onTabChange={key => { setFilter(FILTERS.find(row => row.key === key) ?? FILTERS[0]); setPage(1); }}
      state={opsQueryState(query, mine ? "your jobs" : "repairs")} isEmpty={!rows.length}
      empty={{ message: mine ? "Nothing is assigned to you right now." : "No issues here. Members' reports land in this queue." }}
      pagination={query.data && query.data.count > 24 ? { page, pageSize: 24, count: query.data.count, onChange: setPage } : undefined}
      body={{ kind: "rows", rows: rows.map(issue => <IssueRow key={issue.id} issue={issue} onOpen={() => onOpen(issue.id)} />) }} />
    {opening ? <OpenIssueDialog makerspaceId={makerspace.id} onClose={() => setOpening(false)} onOpened={onOpen} /> : null}
  </>;
}

function IssueRow({ issue, onOpen }: { issue: Issue; onOpen: () => void }) {
  const who = issue.assignees.map(row => row.name).join(", ");
  return <ListRow title={issue.title} onClick={onOpen} identity={{ kind: "icon", icon: "Wrench", tone: "accent" }}
    meta={[`${AREA_LABELS[issue.area]}: ${issue.subject_label}`, who ? `With ${who}` : "",
      new Date(issue.created_at).toLocaleDateString()].filter(Boolean).join(" · ")}
    right={<span className="flex flex-wrap gap-1.5"><StatusPill tone={stateTone(issue.state)} label={STATE_LABELS[issue.state]} />
      {issue.quote_state === "pending" ? <StatusPill tone="warn" label="Quote to approve" /> : null}
      {issue.priority === "urgent" || issue.priority === "high" ? <StatusPill tone="danger" label={issue.priority === "urgent" ? "Urgent" : "High"} /> : null}
    </span>} />;
}
