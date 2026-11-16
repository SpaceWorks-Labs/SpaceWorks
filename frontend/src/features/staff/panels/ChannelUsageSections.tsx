import { t } from "@lingui/core/macro";
import { formatLocale } from "../../../lib/format";
import { reportFieldLabel } from "./reportFieldLabels";
import type { accountTotals, appVersions, flowShares } from "./channelUsage";

const count = (value: number) => value.toLocaleString(formatLocale());
const Empty = ({ children }: { children: string }) => <p className="text-sm text-muted">{children}</p>;

export function AccountsSection({ items }: { items: ReturnType<typeof accountTotals> }) {
  return <section aria-label={t`Active accounts by channel`}>
    <h4 className="title-section mb-2">{t`Active accounts`}</h4>
    {items.length ? <ul className="grid gap-3 sm:grid-cols-3">{items.map(item => <li key={item.channel} className="rounded-lg border border-line p-3">
      <p className="text-sm text-muted">{reportFieldLabel(item.channel)}</p>
      <p className="text-2xl font-semibold">{count(item.active)}</p>
      <p className="text-xs text-muted">{t`${count(item.fresh)} new · ${count(item.returning)} returning`}</p>
    </li>)}</ul> : <Empty>{t`No active accounts recorded in this period.`}</Empty>}
  </section>;
}

export function FlowsSection({ items }: { items: ReturnType<typeof flowShares> }) {
  return <section aria-label={t`Key flows by channel`}>
    <h4 className="title-section mb-2">{t`Key flows by channel`}</h4>
    {items.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <caption className="sr-only">{t`Completed flows and each channel's share`}</caption>
      <thead><tr><th scope="col" className="p-2">{t`Flow`}</th><th scope="col" className="p-2">{t`Completed`}</th><th scope="col" className="p-2">{t`Share by channel`}</th></tr></thead>
      <tbody>{items.map(item => <tr key={item.flow}>
        <th scope="row" className="p-2">{reportFieldLabel(item.flow)}</th><td className="p-2 tabular-nums">{count(item.total)}</td>
        <td className="p-2">{item.channels.map(c => `${reportFieldLabel(c.channel)} ${c.share}%`).join(" · ")}</td></tr>)}</tbody>
    </table></div> : <Empty>{t`No completed flows recorded in this period.`}</Empty>}
  </section>;
}

export function VersionsSection({ items }: { items: ReturnType<typeof appVersions> }) {
  return <section aria-label={t`App versions`}>
    <h4 className="title-section mb-2">{t`App versions in use`}</h4>
    {items.length ? <div className="grid gap-3 sm:grid-cols-2">{items.map(group => <div key={group.channel} className="rounded-lg border border-line p-3">
      <p className="mb-1 font-medium">{reportFieldLabel(group.channel)}</p>
      <ol className="space-y-1 text-sm">{group.versions.map(v => <li key={v.version} className="flex justify-between gap-3">
        <span>{v.version === "unknown" ? t`Unknown` : v.version}</span><span className="tabular-nums text-muted">{count(v.value)} · {v.share}%</span></li>)}</ol>
    </div>)}</div> : <Empty>{t`No app builds reported. Apps send their version in the X-SpaceWorks-App-Version header.`}</Empty>}
  </section>;
}
