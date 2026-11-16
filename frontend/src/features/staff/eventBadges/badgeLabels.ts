// Translated names for the badge designer. Functions, so each call reads the active locale.
import { t } from "@lingui/core/macro";

import type { BadgeElement, BadgeTemplate } from "./badgeGeometry";

export function elementLabels(): Record<BadgeElement, string> {
  return {
    header: t`Heading`, name: t`Attendee name`, email: t`Email`, details: t`Registration answers`, qr: t`Check-in QR`,
    footer: t`Footer`, logo: t`Organisation logo`, eventLogo: t`Event logo`, symbol: t`Space Works symbol`, photo: t`Photo`,
    sponsors: t`Sponsor logos`, idNumber: t`ID number`, validUntil: t`Valid until`,
  };
}

export function colourLabels(): Record<string, string> {
  return {
    auto: t`Automatic`, white: t`White`, cream: t`Warm Cream`, ink: t`Deep Ink`, teal: t`Maker Teal`,
    orange: t`Workshop Orange`, citron: t`Citron`, sky: t`Sky Blue`, yellow: t`Warm Yellow`, event: t`Event accent`,
  };
}

export function templateOptions(): { key: BadgeTemplate; label: string; hint: string }[] {
  return [
    { key: "classic", label: t`Classic`, hint: t`Thin frame, rule under the heading` },
    { key: "bold", label: t`Bold`, hint: t`Heading on a colour band, name in capitals` },
    { key: "minimal", label: t`Minimal`, hint: t`No lines, just the name` },
  ];
}

export function presetLabels(): Record<string, { label: string; detail: string }> {
  return {
    a6: { label: t`A6`, detail: t`105 × 148 mm · sheet paper` },
    "4x6": { label: t`4 × 6 in`, detail: t`Label printer badge` },
    "3x4": { label: t`3 × 4 in`, detail: t`Lanyard pouch badge` },
    "4x3": { label: t`4 × 3 in`, detail: t`Landscape pouch badge` },
    cr80: { label: t`ID card (CR80)`, detail: t`85.6 × 54 mm · PVC card` },
  };
}

export type BadgeRole = "attendee" | "crew" | "volunteer" | "speaker" | "mentor" | "judge" | "organiser";

export function roleLabels(): Record<BadgeRole, string> {
  return { attendee: t`Attendee`, crew: t`Crew`, volunteer: t`Volunteer`, speaker: t`Speaker`, mentor: t`Mentor`,
    judge: t`Judge`, organiser: t`Organiser` };
}

/**
 * - saved: the server has this design
 * - pending: changed here, saving shortly
 * - saving: being saved
 * - local: kept on this device only (offline); saves when back online
 * - error: the last save failed (including someone else saving first)
 */
export type BadgeSaveStatus = "saved" | "pending" | "saving" | "local" | "error";

export function saveStatusLabels(): Record<BadgeSaveStatus, string> {
  return { saved: t`Saved`, pending: t`Unsaved changes`, saving: t`Saving…`, local: t`Saved on this device only`, error: t`Not saved` };
}
