import { t } from "@lingui/core/macro";
import { BoxArt } from "../../../components/BoxSpinner";
import type { ReactNode } from "react";
import { useSyncExternalStore } from "react";
import { RefreshCw } from "lucide-react";
import { illustrationImageProps, type IllustrationId } from "../../../assets/illustrations";
import { RouteLink } from "../../../components/ui/RouteLink";
import { currentTheme, subscribeTheme } from "../../../lib/theme";

function subscribeOnline(callback: () => void) {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => { window.removeEventListener("online", callback); window.removeEventListener("offline", callback); };
}
const onlineNow = () => navigator.onLine;

/** One theme's programme illustration (never both twins), decorative beside its own heading. */
function Mood({ id }: { id: IllustrationId }) {
  const theme = useSyncExternalStore(subscribeTheme, currentTheme);
  const { src, ...art } = illustrationImageProps(id, theme === "dark" ? "dark" : "light");
  return <img src={src} {...art} className="sw-spaces-state-art" />;
}

function StatePanel({ art, title, tone = "neutral", live, children, actions }: {
  art: IllustrationId; title: string; tone?: "neutral" | "error"; live?: "status" | "alert"; children: ReactNode; actions?: ReactNode;
}) {
  return <div className="sw-spaces-state" data-tone={tone} role={live}>
    <Mood id={art} />
    <div className="grid min-w-0 gap-2">
      <h3 className="sw-spaces-state-title">{title}</h3>
      <div className="grid gap-2 text-[15px] leading-6 text-muted">{children}</div>
      {actions ? <div className="mt-2 flex flex-wrap gap-3">{actions}</div> : null}
    </div>
  </div>;
}

/** Replaces the grid when the directory cannot load; offline gets its own wording. */
export function SpacesError({ onRetry, retrying }: { onRetry: () => void; retrying?: boolean }) {
  const online = useSyncExternalStore(subscribeOnline, onlineNow, () => true);
  return <StatePanel art="moods/error" tone="error" live="alert"
    title={online ? t`Couldn't load spaces` : t`You're offline`}
    actions={<button type="button" className="desk-button-primary gap-2" onClick={onRetry} disabled={retrying}>
      {retrying ? <BoxArt size={18} mono /> : <RefreshCw aria-hidden="true" size={18} />}{retrying ? t`Retrying` : t`Retry`}
    </button>}>
    <p>{online ? t`The list didn't arrive. Check your connection and try again.` : t`Spaces load again as soon as you're back online.`}</p>
  </StatePanel>;
}

/** A directory with no public spaces: what to expect, and the way in for whoever is setting it up. */
export function SpacesEmpty({ hosting }: { hosting: boolean }) {
  return <StatePanel art="moods/empty" title={t`No public spaces yet`} live="status"
    actions={<>
      {hosting ? <RouteLink href="/hosting" className="desk-button-primary">{t`Host your makerspace`}</RouteLink> : null}
      <RouteLink href="/admin" className={hosting ? "desk-button" : "desk-button-primary"}>{t`Platform sign-in`}</RouteLink>
    </>}>
    <p>{t`Spaces appear here once they publish their public site.`}</p>
    <p>{t`Setting up Space Works? Sign in to the platform console to create the first space and turn on its public site.`}</p>
  </StatePanel>;
}

/** Search or filter matched nothing; the way back is one button. */
export function SpacesNoResults({ query, onClear }: { query: string; onClear: () => void }) {
  const trimmed = query.trim();
  return <StatePanel art="moods/empty" title={trimmed ? t`No spaces match “${trimmed}”` : t`No spaces in this place`} live="status"
    actions={<button type="button" className="desk-button" onClick={onClear}>{t`Clear filters`}</button>}>
    <p>{t`Try another name, code or place.`}</p>
  </StatePanel>;
}
