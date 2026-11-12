import { t } from "@lingui/core/macro";
import { BoxArt } from "../../components/BoxSpinner";
import { ArrowRight, RefreshCw } from "lucide-react";
import { useSyncExternalStore, type ReactNode } from "react";
import { illustrationImageProps, type IllustrationId } from "../../assets/illustrations";
import { RouteLink } from "../../components/ui/RouteLink";
import { currentTheme, subscribeTheme } from "../../lib/theme";
import { spaceTone } from "../discover/spaces/SpaceCard";
import { canonicalHref, type DirectoryOrganization } from "./publicDirectoryApi";
import "../discover/spaces/spaces.css";

const initial = (name: string) => (Array.from(name.trim())[0] ?? "?").toLocaleUpperCase();

/**
 * One listed organization, in the spaces directory's card vocabulary (one link per card, colour-only
 * hover): the brand field stencilled with its initial, its logo or initial tile, name and summary.
 */
export function OrganizationCard({ row }: { row: DirectoryOrganization }) {
  const tone = spaceTone(row.slug);
  return <article className="sw-space-card" data-tone={tone}>
    <div className="sw-space-field" data-tile={tone}><span className="sw-space-stencil" aria-hidden="true">{initial(row.name)}</span></div>
    <div className="sw-space-body">
      <span className={`sw-space-mark${row.logo_url ? " sw-space-mark-logo" : ""}`} aria-hidden="true">
        {row.logo_url ? <img src={row.logo_url} alt="" loading="lazy" className="h-full w-full object-contain" /> : initial(row.name)}
      </span>
      <h3 className="sw-space-name"><RouteLink className="sw-space-link" href={canonicalHref(row, `/o/${encodeURIComponent(row.slug)}`)}>{row.name}</RouteLink></h3>
      {row.description ? <p className="line-clamp-3 text-sm leading-5 text-muted">{row.description}</p> : null}
      <div className="sw-space-foot"><span className="sw-space-go" aria-hidden="true"><ArrowRight size={20} /></span></div>
    </div>
  </article>;
}

function Mood({ id }: { id: IllustrationId }) {
  const theme = useSyncExternalStore(subscribeTheme, currentTheme);
  const { src, ...art } = illustrationImageProps(id, theme === "dark" ? "dark" : "light");
  return <img src={src} {...art} className="sw-spaces-state-art" />;
}

/** A state that takes the grid's place: illustration, heading, plain words and at most a couple of actions. */
export function DirectoryState({ art, title, tone = "neutral", live, children, actions }: {
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

export function DirectoryError({ onRetry, retrying }: { onRetry: () => void; retrying?: boolean }) {
  return <DirectoryState art="moods/error" tone="error" live="alert" title={t`Couldn't load organizations`}
    actions={<button type="button" className="desk-button-primary gap-2" onClick={onRetry} disabled={retrying}>
      {retrying ? <BoxArt size={18} mono /> : <RefreshCw aria-hidden="true" size={18} />}{retrying ? t`Retrying` : t`Retry`}
    </button>}>
    <p>{t`The list didn't arrive. Check your connection and try again.`}</p>
  </DirectoryState>;
}
