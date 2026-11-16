import { t } from "@lingui/core/macro";

/** Translated names for notification `feature` families (inbox filter and preference centre). */
export const NOTIFICATION_FAMILIES: Record<string, string> = { hardware_requests: t`Hardware`, printing: t`Printing`, events: t`Events`,
  bookings: t`Bookings`, maintenance: t`Maintenance`, members: t`Members`, payments: t`Payments`, stock: t`Stock`,
  certifications: t`Machine access`, devices: t`Devices`, api_access: t`API access`, presence: t`Presence`,
  // Display-only families the inbox carves out of `payments` (shop_*) and `maintenance` (incident_reported).
  shop: t`Shop`, safety: t`Safety` };

export const familyLabel = (feature: string) => NOTIFICATION_FAMILIES[feature] ?? feature.replace(/_/g, " ");
