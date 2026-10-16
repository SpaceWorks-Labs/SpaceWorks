import type { StaffRole } from "./rolesApi";

const descriptions: Record<string, string> = {
  space_manager: "Manages this makerspace, its staff, settings and all workflows.",
  inventory_manager: "Manages inventory and the full hardware loan lifecycle.",
  machine_manager: "Manages machines and service work within this person's assigned machine types.",
  event_manager: "Manages events and registrations, event reports and email templates.",
  booking_manager: "Manages bookable spaces, bookings, booking rules, reports and email templates.",
  handover: "Issues accepted requests and direct handouts, processes returns and hands over completed machine jobs.",
  member: "Uses member services without staff management access.",
};

export function RolesReference({ roles }: { roles: StaffRole[] }) {
  return <details className="rounded-md border border-line bg-bg">
    <summary className="min-h-11 cursor-pointer px-3 py-2 font-semibold text-ink">Roles</summary>
    <dl className="grid gap-3 border-t border-line p-3 text-sm">
      {roles.map((role) => <div key={role.id}><dt className="font-semibold text-ink">{role.name}</dt><dd className="text-muted">{descriptions[role.slug]}</dd></div>)}
    </dl>
  </details>;
}
