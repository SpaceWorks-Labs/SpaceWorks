import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { persistSelectedMakerspace } from "../staffTabs";

/** Opens one space's console page as the superadmin: remember the space for the platform session, then load the page. */
export function openSpaceTab(makerspaceId: number, path: string) {
  persistSelectedMakerspace(makerspaceId, "platform");
  window.location.assign(consoleSessionHref(path, "platform"));
}
