import { useQuery } from "@tanstack/react-query";
import { DetailDrawer, ErrorText, KeyValueCard, ListRow, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { getSpaceHealth, healthKey, type HealthCard } from "./spacesApi";

const STATUS = { ok: ["OK", "success"], warn: ["Warning", "warn"], error: ["Error", "danger"] } as const;

/** One space's health in full: the same facts as its card plus the problems check. */
export function SpaceDetailDrawer({ card, onClose }: { card: HealthCard; onClose: () => void }) {
  const detail = useQuery({ queryKey: [...healthKey, "detail", card.id], queryFn: () => getSpaceHealth(card.id) });
  const data = detail.data;
  return <DetailDrawer open title={card.name} onClose={onClose}>
    {detail.isLoading ? <Skeleton className="h-40 w-full" /> : detail.isError ? <ErrorText resource="this space's health" onRetry={() => { void detail.refetch(); }} /> : data ? <div className="grid gap-6">
      <KeyValueCard title="Space" items={[
        { label: "Web address", value: `/m/${data.slug}` },
        { label: "Created", value: <RelativeTime date={data.created_at} exact /> },
        { label: "Archived", value: data.archived_at ? <RelativeTime date={data.archived_at} exact /> : "No" },
        { label: "Modules", value: data.modules.length ? data.modules.join(", ") : "None" },
        ...(data.schedule ? [{ label: "Schedule note", value: data.schedule.note || "No note" },
          { label: "Reminders sent", value: data.schedule.reminders_sent.length ? data.schedule.reminders_sent.join(", ") : "None yet" }] : []),
      ]} />
      {data.usage.resources.length ? <KeyValueCard title="Usage" items={data.usage.resources.map(row => ({ label: row.label,
        value: `${row.used ?? "?"}${row.limit !== null ? ` of ${row.limit}` : ""}${row.percent !== null ? ` (${Math.round(row.percent)}%)` : ""}` }))} /> : null}
      <section aria-labelledby="space-problems" className="grid gap-3">
        <h3 id="space-problems" className="title-panel">Problems</h3>
        {data.problems.length ? data.problems.map((problem, index) => <ListRow key={`${problem.key}:${index}`} title={problem.message}
          meta={<StatusPill label={STATUS[problem.status][0]} tone={STATUS[problem.status][1]} />}
          right={problem.fix_url ? <a className="desk-button" href={consoleSessionHref(problem.fix_url, "platform")}>Fix</a> : undefined} />)
          : <p className="text-sm text-muted">No problems found for this space.</p>}
      </section>
    </div> : null}
  </DetailDrawer>;
}
