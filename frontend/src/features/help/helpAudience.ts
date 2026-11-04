import type { StaffAuthUser } from "../../lib/api";
import { HELP_SECTIONS, SECTION_BY_ID } from "./helpSections";
import type { HelpArticle, HelpReader, HelpSection, HelpSpace } from "./helpTypes";

export const ANONYMOUS_READER: HelpReader = {
  signedIn: false, superadmin: false, actions: new Set(), eventGrants: false, bookingGrants: false,
};

/** The reader as the auth payload describes them: actions are unioned across every space. */
export function readerFromUser(user: StaffAuthUser | null | undefined): HelpReader {
  if (!user) return ANONYMOUS_READER;
  const superadmin = user.kind === "platform" || Boolean(user.is_platform);
  const actions = new Set<string>([
    ...(user.superadmin_actions ?? []),
    ...user.makerspaces.flatMap(space => space.actions ?? []),
  ]);
  return {
    signedIn: true, superadmin, actions,
    eventGrants: Boolean(user.event_grants?.length), bookingGrants: Boolean(user.booking_grants?.length),
  };
}

export function sectionVisible(section: HelpSection, reader: HelpReader): boolean {
  if (reader.superadmin) return true;
  const { audience } = section;
  if (audience.everyone) return true;
  if (audience.platform) return false;
  if (audience.spaceManager && reader.actions.has("manage_makerspace")) return true;
  if (audience.actions?.some(action => reader.actions.has(action))) return true;
  if (audience.grants?.includes("events") && reader.eventGrants) return true;
  return Boolean(audience.grants?.includes("bookings") && reader.bookingGrants);
}

/** Whether the space (when one is known) runs anything the article is about. */
export function articleFitsSpace(article: HelpArticle, space: HelpSpace | null | undefined): boolean {
  if (!space) return true;
  if (article.modules.length && !article.modules.some(key => space.modules.includes(key))) return false;
  return !article.features.length || article.features.some(key => space.features.includes(key));
}

export function articleVisible(article: HelpArticle, reader: HelpReader, space?: HelpSpace | null): boolean {
  const section = SECTION_BY_ID.get(article.section);
  if (!section) return false;
  const byRole = sectionVisible(section, reader) || article.actions.some(action => reader.actions.has(action));
  return byRole && articleFitsSpace(article, space);
}

export function visibleArticles(articles: readonly HelpArticle[], reader: HelpReader, space?: HelpSpace | null) {
  return articles.filter(article => articleVisible(article, reader, space));
}

/** Sections in reading order that hold at least one article this reader may see. */
export function visibleSections(articles: readonly HelpArticle[], reader: HelpReader, space?: HelpSpace | null) {
  const shown = new Set(visibleArticles(articles, reader, space).map(article => article.section));
  return HELP_SECTIONS.filter(section => shown.has(section.id));
}
