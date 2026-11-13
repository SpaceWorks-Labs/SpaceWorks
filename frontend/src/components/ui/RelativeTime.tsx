import { formatLocale } from "../../lib/format";
import { plural, t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
export type RelativeTimeProps = { date: string | number | Date; now?: string | number | Date;
  /** Also print the exact date and time: audit-grade records must not hide it behind a hover title, which touch screens never show. */
  exact?: boolean;
  /** Lower-case the first letter so it reads mid-sentence ("Due in 2 days", not "Due In 2 days"). */
  inline?: boolean };
export function formatRelativeTime(date: Date, now: Date): string {
  const delta = date.getTime() - now.getTime();
  if (!Number.isFinite(delta)) return t`Unknown time`;
  const minutes = Math.round(Math.abs(delta) / 60000);
  const dayStart = (value: Date) => Date.UTC(value.getFullYear(), value.getMonth(), value.getDate());
  const days = Math.round((dayStart(date) - dayStart(now)) / 86400000);
  if (days === -1) return t`Yesterday`;
  if (days === 1) return t`Tomorrow`;
  if (Math.abs(days) >= 2) return days > 0 ? t`In ${days} days` : t`${-days} days ago`;
  if (minutes < 1) return t`Just now`;
  if (minutes < 60) return delta > 0 ? t`In ${minutes} min` : t`${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  return delta > 0 ? plural(hours, { one: "In # hour", other: "In # hours" }) : plural(hours, { one: "# hour ago", other: "# hours ago" });
}
const midSentence = (text: string, inline: boolean) => inline ? text.charAt(0).toLocaleLowerCase() + text.slice(1) : text;
export function RelativeTime({ date, now, exact = false, inline = false }: RelativeTimeProps) {
  const [clock, setClock] = useState(() => Date.now());
  useEffect(() => {
    if (now !== undefined) return;
    setClock(Date.now());
    const timer = setInterval(() => setClock(Date.now()), 60000);
    return () => clearInterval(timer);
  }, [now]);
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return <span>{t`Unknown time`}</span>;
  return <time dateTime={parsed.toISOString()} title={parsed.toLocaleString(formatLocale())}>
    {midSentence(formatRelativeTime(parsed, new Date(now ?? clock)), inline)}{exact ? <span className="text-muted"> · {parsed.toLocaleString(formatLocale())}</span> : null}</time>;
}
