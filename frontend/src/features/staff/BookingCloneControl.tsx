import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ErrorText, SettingsSection } from "../../components/ui";
import type { BookableSpace } from "./bookingsApi";
import { useCloneBookingSpace } from "./bookingToolsApi";
import { BoxArt } from "../../components/BoxSpinner";

export function BookingCloneControl({ space }: { space: BookableSpace }) {
  const [copyRules, setCopyRules] = useState(false);
  const clone = useCloneBookingSpace(space.makerspace_id, space.id);
  return <SettingsSection title={t`Clone resource`} description={t`Creates an active, private copy with fresh images and default booking rules. Reservations and staff access stay with this resource.`}>
    <div className="grid gap-3 py-5">
      {space.can_copy_booking_rules ? <label className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" checked={copyRules} disabled={clone.isPending} onChange={(event) => setCopyRules(event.target.checked)} />{t`Copy booking rules`}</label> : null}
      <button className="desk-button w-fit" type="button" disabled={clone.isPending} onClick={() => clone.mutate(copyRules && Boolean(space.can_copy_booking_rules))}>{clone.isPending ? <><BoxArt size={16} mono />{t`Cloning...`}</> : t`Create private copy`}</button>
      {clone.error ? <ErrorText message={clone.error.message} /> : null}
      {clone.data ? <p role="status" className="text-sm text-success-ink">{t`Created ${clone.data.name}. Find the private copy in the resource list.`}</p> : null}
    </div>
  </SettingsSection>;
}
