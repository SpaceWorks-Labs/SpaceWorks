import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ListLayout } from "../../../components/layouts";
import { ListRow, StatusPill } from "../../../components/ui";
import type { Makerspace } from "../panels/shared";
import { opsQueryState } from "../opsPresentation";
import { useUrlListState } from "../../../lib/useUrlListState";
import { SavedViewsMenu } from "../SavedViewsMenu";
import { OpenIssueDialog } from "./OpenIssueDialog";
import { AREA_LABELS, STATE_LABELS, stateTone, useIssues, useMyJobs, type Issue } from "./repairsApi";

const FILTERS = [
  { key: "open", label: t`Open`, query: "state=reported,triaged,assigned,in_progress" },
  { key: "reported", label: t`New reports`, query: "state=reported" },
  { key: "done", label: t`Fixed and closed`, query: "state=fixed,closed,rejected" },
];

/** The repairs queue (managers) or "My jobs" (a Technician's assigned jobs), 24 per page. The state tab
 * and page live in the URL (`rp_state`, `rp_page`) so a saved view (A17) or a shared link restores them. */
export function IssueQueue({ makerspace, mine, canOpen, onOpen }: {
  makerspace: Makerspace; mine: boolean; canOpen: boolean; onOpen: (id: number) => void;
}) {
  const list = useUrlListState({ state: "open", page: "1" }, "rp_");
  const filter = FILTERS.find(row => row.key === list.values.state) ?? FILTERS[0];
  const page = list.page;
  const setPage = (next: number) => list.setPage(next);
  const [opening, setOpening] = useState(false);
  const queue = useIssues(makerspace.id, `${filter.query}&page=${page}`, !mine);
  const own = useMyJobs(makerspace.id, page, mine);
  const query = mine ? own : queue;
  const rows = query.data?.results ?? [];
  return <>
    <ListLayout header={{ title: mine ? t`My jobs` : t`Repairs`, subtitle: mine
      ? t`Repair jobs assigned to you. Open one to log visits, parts and the fix.`
      : t`Problems members reported and repair jobs staff opened, from report to fix.`,
      primary: canOpen && !mine ? { label: t`New repair job`, icon: "Plus", onClick: () => setOpening(true) } : undefined }}
      tabs={mine ? undefined : FILTERS.map(row => ({ key: row.key, label: row.label }))} activeTab={filter.key}
      onTabChange={key => list.setFilter("state", key)}
      filters={mine ? undefined : { views: <SavedViewsMenu makerspaceId={makerspace.id} entity="repairs" state={list.values} onRestore={list.restore} /> }}
      state={opsQueryState(query, mine ? "your jobs" : "repairs")} isEmpty={!rows.length}
      empty={{ message: mine ? t`Nothing is assigned to you right now.` : t`No issues here. Members' reports land in this queue.` }}
      pagination={query.data && query.data.count > 24 ? { page, pageSize: 24, count: query.data.count, onChange: setPage } : undefined}
      body={{ kind: "rows", rows: rows.map(issue => <IssueRow key={issue.id} issue={issue} onOpen={() => onOpen(issue.id)} />) }} />
    {opening ? <OpenIssueDialog makerspaceId={makerspace.id} onClose={() => setOpening(false)} onOpened={onOpen} /> : null}
  </>;
}

function IssueRow({ issue, onOpen }: { issue: Issue; onOpen: () => void }) {
  const who = issue.assignees.map(row => row.name).join(", ");
  return <ListRow title={issue.title} onClick={onOpen} identity={{ kind: "icon", icon: "Wrench", tone: "accent" }}
    meta={[`${AREA_LABELS[issue.area]}: ${issue.subject_label}`, who ? `With ${who}` : "",
      new Date(issue.created_at).toLocaleDateString(formatLocale())].filter(Boolean).join(" · ")}
    right={<span className="flex flex-wrap gap-1.5"><StatusPill tone={stateTone(issue.state)} label={STATE_LABELS[issue.state]} />
      {issue.quote_state === "pending" ? <StatusPill tone="warn" label={t`Quote to approve`} /> : null}
      {issue.priority === "urgent" || issue.priority === "high" ? <StatusPill tone="danger" label={issue.priority === "urgent" ? t`Urgent` : t`High`} /> : null}
    </span>} />;
}
