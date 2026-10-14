import { useEffect, useState } from "react";

export function countdownText(startsAt: string, endsAt: string, now: number) {
  const starts = Date.parse(startsAt); const ends = Date.parse(endsAt);
  if (!Number.isFinite(starts) || !Number.isFinite(ends)) return "";
  if (now >= ends) return "Event ended";
  if (now >= starts) return "Happening now";
  const minutes = Math.ceil((starts - now) / 60_000);
  if (minutes >= 1440) return `Starts in ${Math.floor(minutes / 1440)}d ${Math.floor((minutes % 1440) / 60)}h`;
  if (minutes >= 60) return `Starts in ${Math.floor(minutes / 60)}h ${minutes % 60}m`;
  return `Starts in ${minutes}m`;
}

export function EventCountdown({ startsAt, endsAt }: { startsAt: string; endsAt: string }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);
  return <p className="mt-2 text-sm font-semibold text-secondary-ink">{countdownText(startsAt, endsAt, now)}</p>;
}
