import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import type { GalleryPresign } from "../../components/ui/galleryUpload";
import { uploadGalleryPhoto } from "../../components/ui/galleryUpload";

/** Hand-typed until the integrator regenerates the OpenAPI client (Phase 2 lane rule). */
export type SpacePhoto = { id: number; url: string; caption: string; position: number; size_bytes: number; created_at: string };
export type SpacePhotoList = { max_photos: number; can_edit: boolean; results: SpacePhoto[] };

export const spacePhotoKey = (spaceId: number) => ["booking-space", spaceId, "photos"] as const;
const base = (spaceId: number) => `/admin/spaces/${spaceId}/photos/`;

export function useSpacePhotos(spaceId: number) {
  return useQuery({ queryKey: spacePhotoKey(spaceId), queryFn: () => staffRequest<SpacePhotoList>(base(spaceId)) });
}

export function useSpacePhotoMutations(spaceId: number) {
  const client = useQueryClient();
  // Public pages read photos through the space projections, so refresh those too.
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: spacePhotoKey(spaceId) }),
    ...["public-spaces", "public-booking-resource", "booking-discover", "public-event-venue"].map(key =>
      client.invalidateQueries({ queryKey: [key] })),
  ]);
  const json = (method: string, path: string, body?: unknown) =>
    staffRequest(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
  const upload = useMutation({
    mutationFn: (file: File) => uploadGalleryPhoto(file, {
      presign: input => staffRequest<GalleryPresign>(`${base(spaceId)}presign/`, { method: "POST", body: JSON.stringify(input) }),
      attach: objectKey => json("POST", base(spaceId), { object_key: objectKey }),
    }),
    onSettled: refresh,
  });
  const caption = useMutation({
    mutationFn: ({ id, caption: value }: { id: number; caption: string }) => json("PATCH", `${base(spaceId)}${id}/`, { caption: value }),
    onSettled: refresh,
  });
  const reorder = useMutation({ mutationFn: (order: number[]) => json("PUT", `${base(spaceId)}order/`, { order }), onSettled: refresh });
  const remove = useMutation({ mutationFn: (id: number) => json("DELETE", `${base(spaceId)}${id}/`), onSettled: refresh });
  return { upload, caption, reorder, remove };
}
