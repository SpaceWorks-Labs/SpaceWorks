import type { TimelineEntry } from "../membershipLifecycleApi";

const date = (value: string) => new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });

/** X28: the membership history in words, newest first. Shared by staff and the member. */
export function MembershipTimeline({ entries }: { entries: TimelineEntry[] }) {
  if (!entries.length) return <p className="text-sm text-muted">No history yet.</p>;
  return <ol className="grid gap-3 border-l border-line pl-4">
    {entries.map((entry, index) => <li key={`${entry.at}-${entry.kind}-${index}`} className="grid gap-0.5">
      <span className="text-sm font-semibold text-ink">{entry.text}</span>
      <span className="text-xs text-muted">
        {date(entry.at)}{entry.lifetime ? " · for life" : entry.until && ["active", "extended", "upcoming"].includes(entry.kind) ? ` · until ${date(entry.until)}` : ""}
      </span>
      {entry.reason ? <span className="text-xs text-muted">“{entry.reason}”</span> : null}
    </li>)}
  </ol>;
}
