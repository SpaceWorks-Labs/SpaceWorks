import { t } from "@lingui/core/macro";
import { useContext } from "react";
import { CircleHelp } from "lucide-react";
import { HELP_FEATURE, helpHref } from "./helpPaths";
import { StaffHelpContext } from "./staffHelpContext";
import { STAFF_SCREEN_HELP, STAFF_SUBSCREEN_HELP } from "./staffScreenHelp";

type SpaceSwitches = { slug: string; enabled_features?: string[] };

/** The help centre is on for this space (a standalone switch: no parent module to check). */
export function helpCentreOn(space: SpaceSwitches | undefined) {
  return !space || (space.enabled_features ?? []).includes(HELP_FEATURE);
}

type Props = {
  /** The article (`section/slug`) the link opens. */
  article: string;
  /** The space the screen belongs to; its `platform.help_centre` switch hides the link. */
  makerspace?: SpaceSwitches;
  /** A single-space origin serves the guide at `/help`, not `/m/<slug>/help`. */
  singleTenant?: boolean;
  /** The superadmin reads the guide in the platform session. */
  platform?: boolean;
  /** Names the topic for screen readers when one page carries more than one Help link. */
  label?: string;
  /** Show `label` instead of plain "Help" (sub-screen links under a page-level Help). */
  showLabel?: boolean;
  className?: string;
};

/** "Help" beside a screen: a deep link into the guide, opened in a new tab so work in progress stays put. */
export function HelpLink({ article, makerspace, singleTenant = false, platform = false, label = t`Help for this page`, className = "", showLabel = false }: Props) {
  if (!helpCentreOn(makerspace)) return null;
  const href = helpHref(article, { slug: singleTenant ? null : makerspace?.slug, platform });
  return <a href={href} target="_blank" rel="noopener" aria-label={t`${label} (opens in a new tab)`} className={`inline-flex min-h-11 items-center gap-1.5 rounded-control px-2 text-sm font-semibold text-accent-ink hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${className}`}>
    <CircleHelp aria-hidden="true" className="size-4" />
    <span>{showLabel ? label : t`Help`}</span>
  </a>;
}

/** The staff console's mount: the Help link for the active tab, when that tab has an article. */
export function StaffScreenHelp({ tab, ...rest }: Omit<Props, "article"> & { tab: string }) {
  const article = STAFF_SCREEN_HELP[tab];
  if (!article || !helpCentreOn(rest.makerspace)) return null;
  return <div className="-mt-1 mb-2 flex justify-end"><HelpLink article={article} {...rest} /></div>;
}

/** A sub-screen's mount (sub-tab, drawer section or dialog): its STAFF_SUBSCREEN_HELP line, inside the staff workspace only. */
export function ScreenHelp({ screen, className = "flex justify-end" }: { screen: string; className?: string }) {
  const place = useContext(StaffHelpContext);
  const entry = STAFF_SUBSCREEN_HELP[screen];
  if (!place || !entry || !helpCentreOn(place.makerspace)) return null;
  // A sub-screen link sits below the console's own "Help": name its topic so the two differ.
  return <div className={className}><HelpLink article={entry.article} label={t`Help with ${entry.topic}`} showLabel {...place} /></div>;
}
