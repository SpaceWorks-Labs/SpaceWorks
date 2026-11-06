import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { KioskLayout } from "../../components/layouts";
import { Card } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { presenceApi, presenceKeys, type PresenceTVRow } from "./api";
import { clockTime, STATUS_LABELS } from "./presenceCopy";

/** The server caches the projection for at most 30 s, so polling faster buys nothing. */
export const TV_REFRESH_MS = 30_000;

function useOnline() {
  const [online, setOnline] = useState(() => typeof navigator === "undefined" || navigator.onLine !== false);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine !== false);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => { window.removeEventListener("online", update); window.removeEventListener("offline", update); };
  }, []);
  return online;
}

export type PresenceNowBoardProps = { slug: string; spaceName: string;
  /** false (module off or bootstrap says so) renders the unavailable state and sends no request. */
  enabled: boolean };

/** The public "who's in now" display. Rows carry only what the privacy rules let through:
 * a name or "A member"/"A guest", a status, an optional public project/event title and a time. */
export function PresenceNowBoard({ slug, spaceName, enabled }: PresenceNowBoardProps) {
  const online = useOnline();
  // refetchIntervalInBackground stays false: a hidden tab (screen off, other tab) stops polling.
  const tv = useQuery({ queryKey: presenceKeys.tv(slug), queryFn: () => presenceApi.tv(slug), enabled: enabled && Boolean(slug),
    refetchInterval: TV_REFRESH_MS, refetchIntervalInBackground: false,
    retry: (count, error) => count < 1 && !(error instanceof StructuredApiError && error.status === 404) });
  const missing = !enabled || (tv.error instanceof StructuredApiError && tv.error.status === 404);
  const rows = tv.data ?? [];
  const canFullscreen = typeof document !== "undefined" && typeof document.documentElement.requestFullscreen === "function";
  const state = missing ? { status: "ready" as const } : tv.isLoading ? { status: "loading" as const }
    : tv.isError && !tv.data ? { status: "error" as const, error: "Couldn't load who's in. Retrying automatically.", onRetry: () => void tv.refetch() } : { status: "ready" as const };
  return <KioskLayout mode="work" state={state}
    isEmpty={missing || (tv.isSuccess && rows.length === 0)}
    empty={{ message: missing ? t`This display isn't available for this makerspace.` : t`No one is checked in right now.` }}
    context={{ title: t`Who's in at ${spaceName}`, subtitle: tv.dataUpdatedAt ? t`Updated ${clockTime(new Date(tv.dataUpdatedAt).toISOString())}` : t`Live presence` }}
    connection={{ online: online && !(tv.isError && tv.data) }}
    headerActions={canFullscreen ? [{ label: t`Full screen`, onClick: () => void document.documentElement.requestFullscreen().catch(() => undefined) }] : []}
    work={{ capture: <ul aria-label={t`People here now`} className="grid gap-3">{rows.map((row, index) => <PresenceTVItem key={`${row.since}-${index}`} row={row} />)}</ul>,
      panel: <Card className="grid gap-4">
        <p className="text-sm text-muted">{t`Here now`}</p>
        <p className="font-accent text-heading text-brand-ink tabular-nums" aria-live="polite">{rows.length}</p>
        <ul className="grid gap-1 text-base">{(["working", "attending_event", "visiting", "guest"] as const).map((status) => {
          const count = rows.filter((row) => row.status === status).length;
          return count ? <li key={status} className="flex justify-between gap-3"><span>{STATUS_LABELS[status]}</span><span className="tabular-nums">{count}</span></li> : null;
        })}</ul>
      </Card> }} />;
}

function PresenceTVItem({ row }: { row: PresenceTVRow }) {
  const detail = row.status === "working" ? row.project_title : row.status === "attending_event" ? row.event_title : undefined;
  return <li className="grid min-w-0 gap-1 rounded-xl border border-line bg-panel p-5">
    <p className="break-words text-2xl font-semibold text-ink">{row.display_name}</p>
    <p className="break-words text-lg text-muted">{STATUS_LABELS[row.status] ?? row.status}{detail ? <> · <span className="text-ink">{detail}</span></> : null}</p>
    <p className="text-base text-muted">{t`Here since `}<time className="tabular-nums" dateTime={row.since}>{clockTime(row.since)}</time></p>
  </li>;
}
