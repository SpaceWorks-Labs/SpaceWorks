import { useOptionalTenant } from "../../lib/tenant";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { EventPurposePicker } from "./EventPurposePicker";

/**
 * "This is for an event" on a machine-time booking form (decision 342). A child component so the space lookup
 * (the picker needs the makerspace id) only runs for machine spaces, never for a room booking.
 */
export function BookingEventPicker({ makerspaceSlug, value, onChange, disabled }: {
  makerspaceSlug: string; value: string; onChange: (eventId: string) => void; disabled?: boolean;
}) {
  const tenant = useOptionalTenant();
  const bootstrap = useTenantBootstrap(makerspaceSlug, tenant?.mode !== "single");
  const makerspaceId = tenant?.mode === "single" ? tenant.bootstrap?.makerspace.id : bootstrap.data?.makerspace.id;
  return <EventPurposePicker makerspaceId={makerspaceId} value={value} onChange={onChange} disabled={disabled} />;
}
