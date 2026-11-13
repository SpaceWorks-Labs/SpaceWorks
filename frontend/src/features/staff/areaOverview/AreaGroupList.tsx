import { plural, t } from "@lingui/core/macro";
import { ChevronDown, ChevronRight } from "lucide-react";

import { formatDate, formatLocale } from "../../../lib/format";
import { formatMoney } from "../../../lib/money";
import { groupLabel } from "./areaGrouping";
import type { AreaFinance, AreaGroup, AreaItem, AreaMoney, AreaSection } from "./areaOverviewApi";

export function moneyText(amount: string | number | null | undefined, currency: string) {
  if (currency) return formatMoney(amount, currency);
  return Number(amount ?? 0).toLocaleString(formatLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 3 });
}

function statusWords(status: string) {
  const words: Record<string, string> = {
    requested: t`Requested`, approved: t`Approved`, ordered: t`Ordered`, received: t`Received`, cancelled: t`Cancelled`,
    reported: t`Reported`, triaged: t`Triaged`, assigned: t`Assigned`, in_progress: t`In progress`, fixed: t`Fixed`,
    closed: t`Closed`, rejected: t`Rejected`, low: t`Running low`, ok: t`Stocked`, active: t`Covered`,
    expiring_soon: t`Expiring soon`, expired: t`Expired`, unknown: t`No warranty date`,
  };
  return words[status] ?? status;
}

function attentionWords(section: AreaSection, count: number) {
  if (section === "finance") return t`${count} unpaid`;
  if (section === "tobuy") return t`${count} waiting for approval`;
  if (section === "consumables") return t`${count} running low`;
  if (section === "repairs") return t`${count} open`;
  return t`${count} expiring or expired`;
}

/** The one-line totals for a group: money in, out, owed and net per currency, or the list's cost. */
export function TotalsLine({ section, finance, money }: { section: AreaSection; finance: AreaFinance[]; money: AreaMoney[] }) {
  if (section === "finance") {
    return <>{finance.map(row => <span key={row.currency} className="whitespace-nowrap">
      {t`In`} {moneyText(row.money_in, row.currency)} · {t`Out`} {moneyText(row.money_out ?? (Number(row.refunds) + Number(row.expenses)), row.currency)}
      {Number(row.owed) ? <> · {t`Owed`} {moneyText(row.owed, row.currency)}</> : null}
      {row.net !== undefined ? <> · {t`Net`} <strong className={Number(row.net) < 0 ? "text-danger" : ""}>{moneyText(row.net, row.currency)}</strong></> : null}
    </span>)}</>;
  }
  if (!money.length || money.every(row => !Number(row.amount))) return null;
  const label = section === "repairs" ? t`Quoted` : t`Estimated cost`;
  return <span>{label} {money.map(row => moneyText(row.amount, row.currency)).join(" · ")}</span>;
}

function ItemRow({ item }: { item: AreaItem }) {
  const detail = item.unit ? `${item.quantity} ${item.unit}` : item.quantity !== undefined ? t`Qty ${item.quantity}` : "";
  return <li className="flex flex-wrap items-baseline justify-between gap-2 border-t border-line py-2 text-sm first:border-t-0">
    <span className="min-w-0 break-words">{item.label}</span>
    <span className="flex flex-wrap gap-3 text-muted">
      <span>{statusWords(item.status)}</span>
      {detail ? <span>{detail}</span> : null}
      {item.amount ? <span className="tabular-nums">{moneyText(item.amount, item.currency ?? "")}</span> : null}
      {item.expires_on ? <span>{t`Until ${formatDate(item.expires_on)}`}</span> : null}
    </span>
  </li>;
}

type ListProps = { section: AreaSection; groups: AreaGroup[]; open: ReadonlySet<string>; onToggle: (path: string) => void;
  parent?: string; depth?: number };

/** Collapsible groups, each with its count, what needs action and its own totals. */
export function AreaGroupList({ section, groups, open, onToggle, parent = "", depth = 0 }: ListProps) {
  return <ul className={depth ? "grid gap-2 border-l border-line pl-3" : "grid gap-3"}>
    {groups.map(group => {
      const path = `${parent}/${group.key}`;
      const expanded = open.has(path);
      const label = groupLabel(group);
      const panel = `area-group-${path.replace(/[^a-z0-9]/gi, "-")}`;
      return <li key={group.key} className={depth ? "" : "rounded-xl border border-line bg-panel p-3"}>
        <button type="button" aria-expanded={expanded} aria-controls={panel} onClick={() => onToggle(path)}
          className="flex min-h-11 w-full flex-wrap items-center gap-x-3 gap-y-1 rounded-control text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
          {expanded ? <ChevronDown aria-hidden="true" size={16} /> : <ChevronRight aria-hidden="true" size={16} />}
          <span className={depth ? "font-semibold" : "title-section"}>{label}</span>
          <span className="text-sm text-muted">{section === "finance" ? plural(group.count, { one: "# entry", other: "# entries" })
            : plural(group.count, { one: "# row", other: "# rows" })}</span>
          {group.attention ? <span className="rounded-full bg-surface px-2 text-xs font-semibold">{attentionWords(section, group.attention)}</span> : null}
          <span className="ml-auto text-sm tabular-nums"><TotalsLine section={section} finance={group.finance} money={group.money} /></span>
        </button>
        {expanded ? <div id={panel} className="mt-2 grid gap-2">
          {group.children.length ? <AreaGroupList section={section} groups={group.children} open={open} onToggle={onToggle}
            parent={path} depth={depth + 1} /> : null}
          {group.items.length ? <ul aria-label={t`Rows in ${label}`}>{group.items.map(item =>
            <ItemRow key={`${item.source ?? ""}-${item.id}`} item={item} />)}</ul> : null}
        </div> : null}
      </li>;
    })}
  </ul>;
}
