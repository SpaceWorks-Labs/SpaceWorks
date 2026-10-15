import { useState } from "react";
import type { BookableSpace } from "./bookingsApi";
import { useCloneBookingSpace } from "./bookingToolsApi";

export function BookingCloneControl({ space }: { space: BookableSpace }) {
  const [copyRules, setCopyRules] = useState(false);
  const clone = useCloneBookingSpace(space.makerspace_id, space.id);
  return <section className="grid gap-2 rounded-lg border border-line p-3" aria-label="Clone resource">
    <h3 className="title-section">Clone resource</h3>
    <p className="text-sm text-muted">Creates an active, private copy with fresh images and default booking rules. Reservations and staff access stay with this resource.</p>
    {space.can_copy_booking_rules ? <label className="flex gap-2 text-sm"><input type="checkbox" checked={copyRules} disabled={clone.isPending} onChange={(event) => setCopyRules(event.target.checked)} />Copy booking rules</label> : null}
    <button className="desk-button w-fit" type="button" disabled={clone.isPending} onClick={() => clone.mutate(copyRules && Boolean(space.can_copy_booking_rules))}>{clone.isPending ? "Cloning..." : "Create private copy"}</button>
    {clone.error ? <p role="alert" className="text-danger">{clone.error.message}</p> : null}
    {clone.data ? <p role="status" className="text-success">Created {clone.data.name}. Find the private copy in the resource list.</p> : null}
  </section>;
}
