import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { DetailDrawer, ErrorText, KeyValueCard, ListRow, RelativeTime, StatusPill } from "../../../components/ui";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { persistSelectedMakerspace } from "../staffTabs";
import { HostingTypeControl } from "./HostingTypeControl";
import { getSpaceHealth, healthKey, type HealthCard } from "./spacesApi";
import { SpaceLimitsSection } from "./SpaceLimitsSection";
import { SubdomainProvisionSection } from "./SubdomainProvisionSection";
import { SpaceSnapshotSection } from "./SpaceSnapshotSection";
import { moduleList } from "../../../lib/moduleLabels";
import { LogoLoader } from "../../../components/LogoLoader";

// A function, not a module constant: `t` must run after the locale is active.
const STATUS = () => ({ ok: [t`OK`, "success"], warn: [t`Warning`, "warn"], error: [t`Error`, "danger"] }) as const;

/** One space's health in full: the same facts as its card plus the problems check. */
export function SpaceDetailDrawer({ card, onClose }: { card: HealthCard; onClose: () => void }) {
  const detail = useQuery({ queryKey: [...healthKey, "detail", card.id], queryFn: () => getSpaceHealth(card.id) });
  const data = detail.data;
  return <DetailDrawer open title={card.name} onClose={onClose}>
    {detail.isLoading ? <LogoLoader size={48} className="min-h-40 py-3" /> : detail.isError ? <ErrorText resource={t`this space's health`} onRetry={() => { void detail.refetch(); }} /> : data ? <div className="grid gap-6">
      <KeyValueCard title={t`Space`} items={[
        { label: t`Web address`, value: `/m/${data.slug}` },
        { label: t`Created`, value: <RelativeTime date={data.created_at} exact /> },
        { label: t`Archived`, value: data.archived_at ? <RelativeTime date={data.archived_at} exact /> : t`No` },
        { label: t`Modules`, value: data.modules.length ? moduleList(data.modules) : t`None` },
        ...(data.schedule ? [{ label: t`Schedule note`, value: data.schedule.note || t`No note` },
          { label: t`Reminders sent`, value: data.schedule.reminders_sent.length ? data.schedule.reminders_sent.join(", ") : t`None yet` }] : []),
      ]} />
      <SubdomainProvisionSection makerspaceId={data.id} />
      <HostingTypeControl makerspaceId={data.id} />
      <SpaceLimitsSection makerspaceId={data.id} />
      {/* Decision 242(l) / 236: queue counts plus usage, shown for Own and Hosted spaces alike. */}
      <SpaceSnapshotSection makerspaceId={data.id} />
      <section aria-labelledby="space-problems" className="grid gap-3">
        <h3 id="space-problems" className="title-panel">{t`Problems`}</h3>
        {data.problems.length ? data.problems.map((problem, index) => <ListRow key={`${problem.key}:${index}`} title={problem.message}
          meta={<StatusPill label={STATUS()[problem.status][0]} tone={STATUS()[problem.status][1]} />}
          right={problem.fix_url ? <a className="desk-button" href={consoleSessionHref(problem.fix_url, "platform")}
            // A30: keep this space selected so "Fix" opens it, under the Platform › Space header.
            onClick={() => persistSelectedMakerspace(data.id, "platform")}>{t`Fix`}</a> : undefined} />)
          : <p className="text-sm text-muted">{t`No problems found for this space.`}</p>}
      </section>
    </div> : null}
  </DetailDrawer>;
}
