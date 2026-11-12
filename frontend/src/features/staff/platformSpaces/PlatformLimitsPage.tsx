import { t } from "@lingui/core/macro";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { SettingsLayout } from "../../../components/layouts";
import { EmptyState, ErrorText, Field, Pagination, ProgressBar, StatusPill } from "../../../components/ui";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import { BulkLimitsApply } from "./BulkLimitsApply";
import { HostingSwitchSection } from "./HostingSwitchSection";
import { LimitDefaultsSection } from "./LimitDefaultsSection";
import { RequestRatesSection } from "./RequestRatesSection";
import { SpaceLimitsSection } from "./SpaceLimitsSection";
import { getSpaceHealth, healthKey, listSpaceHealth, PAGE_SIZE, percentLevel, type HealthCard } from "./spacesApi";
import { LogoLoader } from "../../../components/LogoLoader";

/** `/admin/platform-limits/<id>` is one space's limits page; the inbox notice's `/admin/platform/spaces/<id>/limits` lands there too. */
export const spaceLimitsHref = (id: number) => consoleSessionHref(`/admin/platform-limits/${id}`, "platform");
export const limitsSpaceId = (pathname: string) => {
  const match = /\/platform-limits\/(\d+)\/?$/.exec(pathname) ?? /\/platform\/spaces\/(\d+)\/limits\/?$/.exec(pathname);
  return match ? Number(match[1]) : null;
};

/** Platform settings opened at `/admin/platform/spaces/<id>/limits` (the limit-reached notice) go to that space's limits page. */
export function PlatformLimitsRedirect({ children }: { children: ReactNode }) {
  const match = /\/platform\/spaces\/(\d+)\/limits\/?$/.exec(useLocation().pathname);
  return match ? <Navigate replace to={spaceLimitsHref(Number(match[1]))} /> : children;
}

function SpaceLimitsRow({ card }: { card: HealthCard }) {
  const peak = card.usage_peak_percent;
  const level = percentLevel(peak);
  return <li className="grid gap-2 border-b border-line py-3 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-center sm:gap-6">
    <div className="grid min-w-0 gap-1">
      <p className="truncate text-sm font-semibold text-ink">{card.name}</p>
      <p className="text-xs text-muted">/m/{card.slug} · {card.hosted ? t`Hosted space` : t`Own space`}</p>
    </div>
    <div className="grid gap-1">
      {peak === null ? <p className="text-xs text-muted">{t`No limits in use`}</p> : <>
        <p className="flex items-center gap-2 text-xs tabular-nums text-muted">{t`Highest use ${Math.round(peak)}%`}
          {level !== "ok" ? <StatusPill label={level === "limit" ? t`At limit` : t`Near limit`} tone={level === "limit" ? "danger" : "warn"} /> : null}</p>
        <ProgressBar value={peak / 100} label={t`${card.name}: highest limit use`} tone={level === "limit" ? "danger" : level === "warning" ? "warn" : "accent"} />
      </>}
    </div>
    <Link className="desk-button min-h-11 justify-self-start" to={spaceLimitsHref(card.id)}>{t`Edit limits`}<span className="sr-only">: {card.name}</span></Link>
  </li>;
}

function SpacesLimitsList() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const term = useDebouncedValue(search.trim(), 300);
  const list = useQuery({ queryKey: [...healthKey, "", term, page], queryFn: () => listSpaceHealth({ search: term, page }), placeholderData: keepPreviousData });
  const rows = list.data?.results ?? [];
  return <div className="grid gap-4">
    <Field label={t`Search spaces`}><input className="desk-input" type="search" value={search} placeholder={t`Name, slug or code`}
      onChange={event => { setSearch(event.target.value); setPage(1); }} /></Field>
    {rows.length ? <BulkLimitsApply spaces={rows} /> : null}
    {list.isLoading ? <LogoLoader size={48} className="min-h-40 py-3" />
      : list.isError ? <ErrorText resource={t`spaces`} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={term ? t`No spaces match this search.` : t`No spaces yet.`} />
      : <ul className="grid" aria-label={t`Spaces and their limits`}>{rows.map(card => <SpaceLimitsRow key={card.id} card={card} />)}</ul>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
  </div>;
}

function OneSpaceLimits({ id }: { id: number }) {
  const detail = useQuery({ queryKey: [...healthKey, "detail", id], queryFn: () => getSpaceHealth(id), retry: false });
  const name = detail.data?.name ?? t`Space #${String(id)}`;
  return <SettingsLayout header={{ title: t`Limits: ${name}`, subtitle: t`Every limit starts as no limit. Usage resets with each limit's period.` }}
    state={{ status: "ready" }} sections={[{ id: "space-limits", rows: <div className="grid gap-4 py-2">
      <Link className="desk-button-ghost min-h-11 w-fit gap-2" to={consoleSessionHref("/admin/platform-limits", "platform")}>
        <ArrowLeft aria-hidden="true" size={16} />{t`All spaces`}</Link>
      <SpaceLimitsSection makerspaceId={id} headingLevel={2} />
    </div> }]} />;
}

/**
 * Limits & hosting (decisions 281, 284, 285): every space's limits with bulk changes, one space's
 * grouped limits editor, whether this install hosts other makerspaces, and the request rates.
 */
export function PlatformLimitsPage() {
  const id = limitsSpaceId(useLocation().pathname);
  if (id) return <OneSpaceLimits id={id} />;
  return <SettingsLayout header={{ title: t`Limits & hosting`, subtitle: t`What each space may use, how often anyone may repeat an action, and whether this install hosts other makerspaces.` }}
    state={{ status: "ready" }} sections={[
      { id: "space-limits", title: t`Space limits`, description: t`Every limit starts as no limit. Open a space to set its limits, or choose several spaces to change the same limits at once.`, rows: <SpacesLimitsList /> },
      { id: "limit-defaults", title: t`Platform default limits`, description: t`The limit every space gets for a key unless it has its own. Every key starts as Unlimited. A space's own limit, or its hosted plan, wins over the default. At 80% staff see a warning; at 100% only new items are refused.`, rows: <LimitDefaultsSection /> },
      { id: "hosting-switch", title: t`Hosting other makerspaces`, description: t`Off by default. Switch it on only if this install will run makerspaces for other groups.`, rows: <HostingSwitchSection /> },
      { id: "request-rates", title: t`Request limits`, description: t`How often one person or address may repeat an action, for every space on this install. The server settings are the standard; a change here must stay within ten times either way.`, rows: <RequestRatesSection /> },
    ]} />;
}
