import { t } from "@lingui/core/macro";
import { TransitionLink } from "../../lib/motion";
import { LogoLoader } from "../../components/LogoLoader";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { groupReports } from "./panels/reportGroups";
import { usePlatformReportCatalog } from "./platformAnalyticsApi";
import { staffTabPath } from "./staffTabs";

/** Superadmin roll-ups, grouped exactly like the module switches. Each opens the Reports hub in its all-makerspaces mode. */
export function PlatformReportGroups() {
  const catalog = usePlatformReportCatalog();
  const reports = Array.isArray(catalog.data?.results) ? catalog.data.results.filter(report => report.available !== false) : [];
  const href = (key: string) => consoleSessionHref(`${staffTabPath("reports", false, undefined)}?scope=all&report=${encodeURIComponent(key)}`);
  return <section aria-label={t`Reports by module`} className="min-w-0 space-y-3 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section">{t`Reports by module`}</h3>
    <p className="text-sm text-muted">{t`Roll-ups across every makerspace, as totals per space. They never contain a person's details.`}</p>
    {catalog.isLoading ? <LogoLoader label={t`Loading reports…`} size={48} className="min-h-16 py-3" /> : catalog.isError ? <div role="alert">
      <p>{t`Couldn't load the report list.`}</p><button type="button" className="desk-button" onClick={() => void catalog.refetch()}>{t`Retry`}</button></div>
      : !reports.length ? <p className="text-sm text-muted">{t`No roll-up reports are available.`}</p>
      : <div className="grid gap-4 sm:grid-cols-2">{groupReports(reports).map(group => <div key={group.key}>
        <h4 className="eyebrow mb-2">{group.label}</h4>
        <ul className="grid gap-1">{group.reports.map(report => <li key={report.key}>
          <TransitionLink className="block min-h-11 rounded-control px-2 py-2 text-sm hover:bg-hover" to={href(report.key)}>{report.title}</TransitionLink></li>)}</ul>
      </div>)}</div>}
  </section>;
}
