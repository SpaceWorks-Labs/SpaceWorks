import { t } from "@lingui/core/macro";
import { Gallery } from "../../components/ui/Gallery";
import type { PublicBookableSpace } from "./publicBookingsApi";

/** The public/member detail-page "Photos" section for a bookable space; omitted when it has none. */
export function photosSection(space: Pick<PublicBookableSpace, "name" | "photos">) {
  const photos = space.photos ?? [];
  return photos.length ? [{ id: "photos", label: t`Photos`, content: <Gallery photos={photos} label={t`Photos of ${space.name}`} /> }] : [];
}
