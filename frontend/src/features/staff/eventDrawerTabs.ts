import { useOpsTabs } from "./opsPresentation";
import type { StaffEvent } from "./eventsApi";
import type { eventAccess } from "./eventStaffPermissions";

/** Everything past the day-of-event work, in the order the "More" tab lists it. */
export const MORE_SECTIONS = [
  { key: "tickets", label: "Tickets & invites" },
  { key: "speakers", label: "Speakers" },
  { key: "feedback", label: "Feedback" },
  { key: "broadcasts", label: "Broadcasts" },
  { key: "analytics", label: "Analytics" },
  { key: "website", label: "Website" },
  { key: "team", label: "Team" },
  { key: "settings", label: "Settings" },
] as const;
export type MoreSection = typeof MORE_SECTIONS[number]["key"];

/**
 * Which drawer surfaces this viewer may open. Every gate mirrors the event staff grant the API
 * enforces, so a grant-only staffer sees exactly the sections whose actions they hold.
 */
export function eventDrawerSurfaces(event: StaffEvent | undefined, access: ReturnType<typeof eventAccess>) {
  const ticketing = event?.ticketing_features ?? [];
  const checkable = event?.status === "published" || event?.status === "completed";
  const invites = access.invitations && ticketing.includes("events.invites");
  const ticketTypes = access.manager && ticketing.includes("events.ticket_types");
  const promos = access.manager && ticketing.includes("events.promo_codes");
  const sections: Record<MoreSection, boolean> = {
    tickets: invites || ticketTypes || promos,
    speakers: access.edit || access.manager,
    feedback: access.edit || access.registrations,
    broadcasts: access.registrations && Boolean(event?.broadcasts_enabled),
    analytics: Boolean(event?.report_features?.includes("analytics")),
    website: ticketing.includes("events.website") && (access.edit || access.publish),
    team: access.manager,
    settings: access.edit || access.publish,
  };
  return {
    ticketing, checkable, invites, ticketTypes, promos, sections,
    // Drafts keep the tab so check-in staff learn when it opens; cancelled events have no door.
    checkInTab: access.checkIn && (checkable || event?.status === "draft"),
  };
}

type Choice = { key: string; label: string; count?: number };

/**
 * Top tabs are Overview, Registrations, Check-in and More. Each More section keeps its own
 * `eventTab` value, so links written before the More tab existed (`?eventTab=tickets`,
 * `?eventTab=settings`, …) still open the right section, and `?eventTab=more` opens the first.
 */
export function useEventDrawerTabs(top: Choice[], sections: Record<MoreSection, boolean>) {
  const available = MORE_SECTIONS.filter((section) => sections[section.key]);
  const more = available.length ? [{ key: "more", label: "More" }] : [];
  const ops = useOpsTabs("eventTab", [...top, ...more, ...available], "overview");
  const section = ops.active === "more" ? available[0]?.key
    : available.find((choice) => choice.key === ops.active)?.key;
  const topKeys = new Set([...top, ...more].map((choice) => choice.key));
  const sectionKeys = new Set<string>(available.map((choice) => choice.key));
  return {
    active: section ? "more" : ops.active,
    section: section as MoreSection | undefined,
    tabs: ops.tabs.filter((tab) => topKeys.has(tab.key)),
    sectionTabs: ops.tabs.filter((tab) => sectionKeys.has(tab.key)),
    select: ops.select,
    onClickCapture: ops.onClickCapture,
  };
}
