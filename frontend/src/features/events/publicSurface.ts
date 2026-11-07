import { t } from "@lingui/core/macro";
/**
 * L1's additions to the public event payload. They live here until the coordinator
 * regenerates `generated/api.ts` at merge; reading them through `surfaceOf` keeps every
 * caller typed without hand-editing the generated file.
 */
export type DeliveryMode = "in_person" | "online" | "hybrid";
export type PublicSurfaceFields = {
  /** False for an unlisted event: the page must carry `noindex, nofollow`. */
  indexable?: boolean;
  /** Null while the space has online events switched off. */
  delivery_mode?: DeliveryMode | null;
};

export const DELIVERY_LABELS: Record<DeliveryMode, string> = { in_person: t`In person`, online: t`Online`, hybrid: t`Hybrid` };

export function surfaceOf(event: object | undefined | null): PublicSurfaceFields {
  return (event ?? {}) as PublicSurfaceFields;
}

/** The mode chip text, or null when the space does not use online events. */
export function deliveryLabel(event: object | undefined | null) {
  const mode = surfaceOf(event).delivery_mode;
  return mode ? DELIVERY_LABELS[mode] : null;
}
