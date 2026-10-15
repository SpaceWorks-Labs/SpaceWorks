import { useEffect, useState } from "react";
export type RelativeTimeProps = { date: string | number | Date; now?: string | number | Date;
  /** Also print the exact date and time: audit-grade records must not hide it behind a hover title, which touch screens never show. */
  exact?: boolean };
export function formatRelativeTime(date: Date, now: Date): string {
  const delta = date.getTime() - now.getTime();
  if (!Number.isFinite(delta)) return "Unknown time";
  const minutes = Math.round(Math.abs(delta) / 60000);
  const dayStart = (value: Date) => Date.UTC(value.getFullYear(), value.getMonth(), value.getDate());
  const days = Math.round((dayStart(date) - dayStart(now)) / 86400000);
  if (days === -1) return "Yesterday";
  if (days === 1) return "Tomorrow";
  if (Math.abs(days) >= 2) return days > 0 ? `In ${days} days` : `${-days} days ago`;
  if (minutes < 1) return "Just now";
  const count = minutes < 60 ? minutes : Math.floor(minutes / 60);
  const unit = minutes < 60 ? "min" : count === 1 ? "hour" : "hours";
  return delta > 0 ? `In ${count} ${unit}` : `${count} ${unit} ago`;
}
export function RelativeTime({ date, now, exact = false }: RelativeTimeProps) {
  const [clock, setClock] = useState(() => Date.now());
  useEffect(() => {
    if (now !== undefined) return;
    setClock(Date.now());
    const timer = setInterval(() => setClock(Date.now()), 60000);
    return () => clearInterval(timer);
  }, [now]);
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return <span>Unknown time</span>;
  return <time dateTime={parsed.toISOString()} title={parsed.toLocaleString()}>
    {formatRelativeTime(parsed, new Date(now ?? clock))}{exact ? <span className="text-muted"> · {parsed.toLocaleString()}</span> : null}</time>;
}
