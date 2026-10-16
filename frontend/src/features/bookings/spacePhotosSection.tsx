import { Gallery } from "../../components/ui/Gallery";
import type { PublicBookableSpace } from "./publicBookingsApi";

/** The public/member detail-page "Photos" section for a bookable space; omitted when it has none. */
export function photosSection(space: Pick<PublicBookableSpace, "name" | "photos">) {
  const photos = space.photos ?? [];
  return photos.length ? [{ id: "photos", label: "Photos", content: <Gallery photos={photos} label={`Photos of ${space.name}`} /> }] : [];
}
