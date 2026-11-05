import { BookableSpaceForm, valuesForSpace } from "./BookableSpaceForm";
import { BookingCloneControl } from "./BookingCloneControl";
import { BookingDetailsEditor } from "./BookingDetailsEditor";
import { BookingStaffAccess } from "./BookingStaffAccess";
import { PriceOverrideCard } from "./pricing/PriceOverrideCard";
import { usePriceDropCheck } from "./priceDrop/usePriceDropCheck";
import type { bookingAccess } from "./bookingStaffPermissions";
import type { BookableSpace, BookableSpacePayload, useUpdateBookableSpace } from "./bookingsApi";

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
  // Lane L24: a cheaper room may owe paid upcoming bookings a refund.
  const drop = usePriceDropCheck(makerspaceId);
  const saveSettings = async (payload: BookableSpacePayload) => {
    const cheaper = payload.payment_amount !== undefined && Number(payload.payment_amount) < Number(space.payment_amount);
    if (cheaper && !(await drop.check(`/admin/spaces/${space.id}/`, "PATCH", payload))) return;
    update.mutate(payload);
  };
  return <div className="grid gap-6">
    {access.manager ? <BookableSpaceForm makerspaceId={makerspaceId} mode="settings" key={space.updated_at} initialValues={valuesForSpace(space)}
      onSubmit={payload => { void saveSettings(payload); }} pending={update.isPending || drop.checking}
      error={error} submitLabel="Save changes" disabled={!space.is_active} />
      : access.edit ? <BookingDetailsEditor key={space.updated_at} space={space} pending={update.isPending} onSubmit={payload => update.mutate(payload)} />
      : <p className="whitespace-pre-wrap text-sm text-muted">{space.description || "Use your assigned resource permissions."}</p>}
    {!space.is_active ? <p className="text-sm text-muted">This space is inactive and read-only.</p> : null}
    {access.manager ? <PriceOverrideCard makerspaceId={makerspaceId} targetType="bookable_space" targetId={space.id} /> : null}
    {access.manager && space.clone_enabled ? <BookingCloneControl space={space} /> : null}
    {access.manager && space.staff_grants_enabled ? <BookingStaffAccess target={{ id: space.id }} /> : null}
    {drop.dialog}
  </div>;
}
