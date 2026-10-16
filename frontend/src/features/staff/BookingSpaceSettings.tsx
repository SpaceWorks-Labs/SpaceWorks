import { BookableSpaceForm, valuesForSpace } from "./BookableSpaceForm";
import { BookingCloneControl } from "./BookingCloneControl";
import { BookingDetailsEditor } from "./BookingDetailsEditor";
import { BookingStaffAccess } from "./BookingStaffAccess";
import type { bookingAccess } from "./bookingStaffPermissions";
import type { BookableSpace, useUpdateBookableSpace } from "./bookingsApi";

/** The Settings tab of one bookable space, narrowed to what this actor may change.
 *
 * A space manager edits every setting, clones the resource and grants staff access; a grantee holding
 * `edit_details` edits the descriptive fields only; anyone else sees the description read-only.
 */
export function BookingSpaceSettings({ makerspaceId, space, access, update }: {
  makerspaceId: number; space: BookableSpace;
  access: ReturnType<typeof bookingAccess>; update: ReturnType<typeof useUpdateBookableSpace>;
}) {
  const error = update.error ? update.error instanceof Error ? update.error.message : "Something went wrong." : undefined;
  return <div className="grid gap-6">
    {access.manager ? <BookableSpaceForm makerspaceId={makerspaceId} mode="settings" key={space.updated_at} initialValues={valuesForSpace(space)}
      onSubmit={payload => update.mutate(payload)} pending={update.isPending}
      error={error} submitLabel="Save changes" disabled={!space.is_active} />
      : access.edit ? <BookingDetailsEditor key={space.updated_at} space={space} pending={update.isPending} onSubmit={payload => update.mutate(payload)} />
      : <p className="whitespace-pre-wrap text-sm text-muted">{space.description || "Use your assigned resource permissions."}</p>}
    {!space.is_active ? <p className="text-sm text-muted">This space is inactive and read-only.</p> : null}
    {access.manager && space.clone_enabled ? <BookingCloneControl space={space} /> : null}
    {access.manager && space.staff_grants_enabled ? <BookingStaffAccess target={{ id: space.id }} /> : null}
  </div>;
}
