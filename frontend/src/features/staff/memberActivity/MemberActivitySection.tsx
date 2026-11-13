import { t } from "@lingui/core/macro";

import { StatusPill } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import { StructuredApiError } from "../../../lib/api";
import { formatDate } from "../../../lib/format";
import { formatMoney } from "../../../lib/money";
import { useCrossLink } from "../crossLinks/staffHref";
import { opsStatusLabel } from "../opsPresentation";
import {
  AREA_LABELS, areaTarget, rowTarget, useMemberActivity, type MemberActivityArea, type MemberActivityBlock,
} from "./memberActivityApi";
import { StaffIncludedHours } from "./StaffIncludedHours";
import { LogoLoader } from "../../../components/LogoLoader";

/**
 * PE1 / decision 242(e): one member's footprint across every area. Every area shows its count
 * and a link into that area; full rows appear only where the server sent them (areas the viewer
 * manages). An area that failed on the server is named, never shown as a silent zero. The
 * whole block disappears for a viewer the server refuses (403) or a member not in this space (404).
 */
export function MemberActivitySection({ makerspaceId, userId }: { makerspaceId: number; userId: number }) {
  const activity = useMemberActivity(makerspaceId, userId);
  const status = activity.error instanceof StructuredApiError ? activity.error.status : undefined;
  const areas = activity.data?.areas ?? [];
  const failed = activity.data?.errors ?? [];
  if (status === 403 || status === 404) return null;
  return <section className="grid min-w-0 gap-3 border-t border-line pt-4" aria-labelledby={`member-activity-${userId}`}>
    <h2 id={`member-activity-${userId}`} className="title-panel">{t`Activity across the space`}</h2>
    {activity.isLoading ? <LogoLoader label={t`Loading activity…`} size={48} className="min-h-16 py-3" /> : null}
    {activity.error ? <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-danger"><p>{t`Couldn't load this member's activity.`}</p>
      <button className="desk-button" type="button" onClick={() => { void activity.refetch(); }}>{t`Retry`}</button></div> : null}
    {activity.data ? <>
      <AccountFacts access={activity.data.access_status} member={activity.data.is_member} />
      <StaffIncludedHours makerspaceId={makerspaceId} userId={userId} />
      {failed.length ? <p role="alert" className="text-sm text-warn-ink">{t`Some areas couldn't be loaded: ${failed.map(area => AREA_LABELS[area as MemberActivityArea] ?? area).join(", ")}.`}</p> : null}
      {areas.length ? <ul className="grid min-w-0 gap-3">
        {areas.map(block => <AreaBlock key={block.area} block={block} userId={userId} />)}
      </ul> : <p className="text-sm text-muted">{t`No activity in this space yet.`}</p>}
    </> : null}
  </section>;
}

/** A26: restriction state first, since it decides whether this person may borrow again. */
function AccountFacts({ access, member }: { access?: string; member?: boolean }) {
  if (access !== "restricted" && access !== "suspended" && member !== false) return null;
  return <div className="flex flex-wrap items-center gap-2 text-sm">
    {access === "restricted" ? <StatusPill tone="warn" label={t`Restricted: cannot borrow until cleared`} /> : null}
    {access === "suspended" ? <StatusPill tone="danger" label={t`Suspended`} /> : null}
    {member === false ? <span className="text-muted">{t`Account only, not a member of this space.`}</span> : null}
  </div>;
}

function AreaBlock({ block, userId }: { block: MemberActivityBlock; userId: number }) {
  const link = useCrossLink();
  const target = areaTarget(block.area, userId);
  const href = block.count ? link(target.tab, target.query, target.subPath) : undefined;
  const facts = [
    block.open ? t`${block.open} out now` : "",
    block.pending ? t`${block.pending} unpaid` : "",
    ...Object.entries(block.owed ?? {}).map(([currency, amount]) => t`${formatMoney(amount, currency)} owed`),
    block.guest_passes ? t`${block.guest_passes} guest passes` : "",
    block.volunteer_entries ? t`${block.volunteer_entries} volunteer entries` : "",
    block.machine_access ? t`${block.machine_access} machine access grants` : "",
  ].filter(Boolean);
  return <li className="grid min-w-0 gap-2 rounded-control border border-line bg-panel p-3">
    <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-2">
      <h3 className="title-section">{AREA_LABELS[block.area]} <span className="tabular-nums text-muted">({block.count})</span></h3>
      {href ? <RouteLink className="text-sm font-semibold underline" href={href}>{t`Open ${AREA_LABELS[block.area]}`}</RouteLink> : null}
    </div>
    {facts.length ? <p className="text-sm text-muted">{facts.join(" · ")}</p> : null}
    {block.rows_visible && block.rows?.length ? <ul className="grid min-w-0 gap-1">{block.rows.map(row => {
      const rowLink = rowTarget(row);
      const rowHref = link(rowLink.tab, rowLink.query, rowLink.subPath);
      const text = <><span className="font-semibold [overflow-wrap:anywhere]">{row.label}</span>
        <span className="text-sm text-muted">{[opsStatusLabel(row.status), row.at ? formatDate(row.at) : ""].filter(Boolean).join(" · ")}</span></>;
      return <li key={`${row.link.tab}-${row.id}`} className="min-w-0">{rowHref
        ? <RouteLink className="flex min-h-11 min-w-0 flex-wrap items-center justify-between gap-2 rounded-control px-2 hover:bg-hover" href={rowHref}>{text}</RouteLink>
        : <span className="flex min-h-11 min-w-0 flex-wrap items-center justify-between gap-2 px-2">{text}</span>}</li>;
    })}</ul> : null}
    {!block.rows_visible && block.count ? <p className="text-xs text-muted">{t`Counts only: this area is managed by someone else.`}</p> : null}
  </li>;
}
