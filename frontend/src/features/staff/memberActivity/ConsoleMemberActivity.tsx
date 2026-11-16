import { MemberActivityDrawer } from "./MemberActivityDrawer";

// The member 360's own area actions (backend views_member_activity._AREA_ACTIONS); a handover-only
// desk holds none of them and the server answers 404, so it is never mounted for them.
const AREA_ACTIONS = [
  "manage_members", "manage_events", "manage_bookings", "manage_machines", "manage_shop", "view_shop", "view_inventory",
  "accept_request", "work_repairs", "run_maintenance", "set_service_state", "view_finance", "record_payment",
];
// Tabs that mount their own drawer (Members, and the Ledger's "Borrower history").
const OWN_DRAWER_TABS = ["members", "ledger"];

/**
 * C30 / A26: `?member=<id>` opens the member 360 on ANY staff tab, so staff without the Members tab
 * (an Inventory, Event, Booking or Shop manager) can still follow a person link from their own area.
 */
export function ConsoleMemberActivity({ makerspaceId, activeTab, actions, isSuperadmin }: {
  makerspaceId: number; activeTab: string; actions: readonly string[]; isSuperadmin: boolean;
}) {
  if (OWN_DRAWER_TABS.includes(activeTab)) return null;
  if (!isSuperadmin && !actions.some(action => AREA_ACTIONS.includes(action))) return null;
  return <MemberActivityDrawer makerspaceId={makerspaceId} />;
}
