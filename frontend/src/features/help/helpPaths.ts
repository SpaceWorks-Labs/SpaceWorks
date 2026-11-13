/** Feature key of the help centre switch (standalone, default on). */
export const HELP_FEATURE = "platform.help_centre";

export type HelpLocation = {
  /** The space slug on the central origin; omitted on a single-space origin or for the platform guide. */
  slug?: string | null;
  /** The superadmin reads the guide in the platform session. */
  platform?: boolean;
};

/** The guide's base path: `/help`, or `/m/<slug>/help` for a space on the central origin. */
export function helpBase({ slug }: HelpLocation = {}) {
  return slug ? `/m/${encodeURIComponent(slug)}/help` : "/help";
}

/** A deep link to an article (`section/slug`), a section, or the guide's front page. */
export function helpHref(target = "", location: HelpLocation = {}) {
  const path = target ? `${helpBase(location)}/${target.split("/").map(encodeURIComponent).join("/")}` : helpBase(location);
  return location.platform ? `${path}?context=platform` : path;
}

/** Keep the platform marker when moving between guide pages. */
export function platformSearch(search: string) {
  return new URLSearchParams(search).get("context") === "platform";
}
