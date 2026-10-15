import { useMemo, type Dispatch, type SetStateAction } from "react";

import { Badge, ErrorBlock, ListRow } from "../../../../components/ui";
import { useCardMemberships, useIssueCard } from "./api";
import { QueryContent } from "../../../../components/layouts/LayoutFrame";
import { opsQueryState, opsStatusLabel } from "../../opsPresentation";
import type { CardMembershipRow } from "./types";

const memberLabel = (row: CardMembershipRow) => row.user.display_name || row.user.username;

/** The issue queue: memberships that hold no active card.
 *
 *  A member already carrying a card is absent rather than disabled — issuing a second one
 *  is the `reissue` action on the card, which is where the lost/stolen reason is recorded.
 */
export function IssueRoster({
  makerspaceId,
  cardedMembershipIds,
  names, setNames, memberships,
}: {
  makerspaceId: number;
  memberships: ReturnType<typeof useCardMemberships>;
  cardedMembershipIds: number[];
  names: Record<number, string>;
  setNames: Dispatch<SetStateAction<Record<number, string>>>;
}) {
  const issue = useIssueCard(makerspaceId);
  const carded = useMemo(() => new Set(cardedMembershipIds), [cardedMembershipIds]);
  const rows = (memberships.data ?? []).filter((row) => !carded.has(row.id));

  return <section aria-label="Members without a card">
    <h2 className="title-section mb-4">Members without a card</h2>
    <QueryContent state={opsQueryState(memberships, "members")} isEmpty={!rows.length}
      empty={{ message: "Every active member has a card." }}>
      <div className="grid gap-3">{rows.map(row => <ListRow key={row.id} title={memberLabel(row)}
        identity={{ kind: "avatar", name: memberLabel(row), seed: String(row.id) }}
        right={<div className="flex flex-wrap items-center gap-3">
          {row.status ? <Badge tone={row.status === "active" ? "success" : "warn"}>{opsStatusLabel(row.status)}</Badge> : null}
          <label className="sr-only" htmlFor={"printed-name-" + row.id}>Printed name for {memberLabel(row)}</label>
          <input id={"printed-name-" + row.id} className="desk-input w-full sm:w-56" placeholder="Printed name (optional)"
            value={names[row.id] ?? ""} onChange={event => setNames({ ...names, [row.id]: event.target.value })} />
          <button className="desk-button" type="button" disabled={issue.isPending}
            onClick={() => issue.mutate({ membershipId: row.id, printedName: names[row.id]?.trim() || undefined })}>
            {issue.isPending && issue.variables?.membershipId === row.id ? "Issuing…" : "Issue card"}</button>
        </div>} />)}</div>
    </QueryContent>
    {issue.error ? <ErrorBlock error={issue.error} /> : null}
  </section>;
}
