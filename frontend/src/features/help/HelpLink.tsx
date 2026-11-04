import { CircleHelp } from "lucide-react";
import { HELP_FEATURE, helpHref } from "./helpPaths";
import { STAFF_SCREEN_HELP } from "./staffScreenHelp";

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
  className?: string;
};

/** "Help" beside a screen: a deep link into the guide, opened in a new tab so work in progress stays put. */
export function HelpLink({ article, makerspace, singleTenant = false, platform = false, className = "" }: Props) {
  if (!helpCentreOn(makerspace)) return null;
  const href = helpHref(article, { slug: singleTenant ? null : makerspace?.slug, platform });
  return <a href={href} target="_blank" rel="noopener" className={`inline-flex min-h-11 items-center gap-1.5 rounded-control px-2 text-sm font-semibold text-accent-ink hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${className}`}>
    <CircleHelp aria-hidden="true" className="size-4" />
    <span>Help<span className="sr-only"> for this page (opens in a new tab)</span></span>
  </a>;
}

/** The staff console's mount: the Help link for the active tab, when that tab has an article. */
export function StaffScreenHelp({ tab, ...rest }: Omit<Props, "article"> & { tab: string }) {
  const article = STAFF_SCREEN_HELP[tab];
  if (!article) return null;
  return <div className="-mt-1 mb-2 flex justify-end"><HelpLink article={article} {...rest} /></div>;
}
