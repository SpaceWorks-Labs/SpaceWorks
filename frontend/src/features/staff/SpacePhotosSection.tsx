import { t } from "@lingui/core/macro";
import { GalleryEditor } from "../../components/ui/GalleryEditor";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { opsQueryState } from "./opsPresentation";
import { useSpacePhotoMutations, useSpacePhotos } from "./spacePhotosApi";

/** Space settings block: the staff side of the shared place-photo gallery. */
export function SpacePhotosSection({ spaceId, active }: { spaceId: number; active: boolean }) {
  const photos = useSpacePhotos(spaceId);
  const { upload, caption, reorder, remove } = useSpacePhotoMutations(spaceId);
  const data = photos.data;
  return (
    <QueryContent state={opsQueryState(photos, "place photos")} isEmpty={false}>
      {data ? (
        <GalleryEditor photos={data.results} maxPhotos={data.max_photos} canEdit={data.can_edit && active}
          readOnlyMessage={!active ? t`Reactivate the space to change its photos.` : t`Only staff who can edit this space's details can change its photos.`}
          onUpload={file => upload.mutateAsync(file)}
          onCaption={(id, value) => caption.mutateAsync({ id, caption: value })}
          onReorder={order => reorder.mutateAsync(order)}
          onRemove={id => remove.mutateAsync(id)} />
      ) : null}
    </QueryContent>
  );
}
