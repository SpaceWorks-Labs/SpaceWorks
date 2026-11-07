import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { StructuredApiError } from "../../lib/api";
import type { PresenceSession, PresenceStatus } from "./api";

export const STATUS_LABELS: Record<PresenceStatus, string> = {
  working: t`Working on a project`,
  visiting: t`Visiting`,
  attending_event: t`Attending an event`,
  guest: t`Guest`,
};

export const STAFF_ALTERNATIVE = "Ask staff at the desk or use the check-in kiosk instead.";

export function presetLabel(minutes: number) {
  if (minutes % 60 === 0) return `${minutes / 60} h`;
  return minutes > 60 ? t`${Math.floor(minutes / 60)} h ${minutes % 60} min` : `${minutes} min`;
}

export function presetLongLabel(minutes: number) {
  if (minutes % 60 === 0) return minutes === 60 ? t`1 hour` : `${minutes / 60} hours`;
  return presetLabel(minutes);
}

export function minutesLeft(session: Pick<PresenceSession, "expires_at">, now: number) {
  return Math.ceil((new Date(session.expires_at).getTime() - now) / 60_000);
}

export function timeLeftLabel(minutes: number) {
  if (minutes <= 0) return t`Ended`;
  if (minutes < 60) return t`${minutes} min left`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? t`${hours} h ${rest} min left` : t`${hours} h left`;
}

export const clockTime = (iso: string) => new Date(iso).toLocaleTimeString(formatLocale(), { hour: "2-digit", minute: "2-digit" });

/** Server refusals that mean "self check-in is not possible from here": always offer the staff route. */
const LOCATION_CODES: Record<string, string> = {
  outside_geofence: "You're outside this makerspace's check-in area, so self check-in is refused.",
  location_inaccurate: "Your location reading isn't precise enough to confirm you're inside. Move nearer a window or step outside briefly, then retry.",
  location_required: "Check-in needs your location, and none was shared.",
  location_invalid: "Your device sent an unreadable location.",
  geofence_unconfigured: "Self check-in isn't set up for this makerspace yet.",
};

export function presenceErrorText(error: unknown): { text: string; staffRoute: boolean } {
  if (error instanceof StructuredApiError) {
    if (error.code && LOCATION_CODES[error.code]) return { text: LOCATION_CODES[error.code], staffRoute: true };
    if (error.code === "walk_in_staff_required") return { text: error.detail ?? t`Ask staff to check you in.`, staffRoute: true };
    if (error.code === "session_expired") return { text: t`That check-in ended too long ago to renew. Check in again.`, staffRoute: false };
    return { text: error.detail ?? error.message, staffRoute: false };
  }
  return { text: error instanceof Error ? error.message : t`Something went wrong. Try again.`, staffRoute: false };
}

/** What the person will look like on the public display, in plain words. */
export function displayDisclosure(session: Pick<PresenceSession, "names_displayed" | "personal_opt_out_allowed" | "hide_on_display">) {
  if (session.names_displayed && !session.personal_opt_out_allowed) return "Your name is shown on this space's “who's in” display. This space shows everyone's name and doesn't offer hiding.";
  if (session.names_displayed) return "Your name is shown on this space's “who's in” display.";
  if (session.hide_on_display) return "You appear as an anonymous visitor on this space's display.";
  return "This space's display doesn't show names, so you appear anonymously.";
}
