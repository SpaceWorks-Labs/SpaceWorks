import { t } from "@lingui/core/macro";

import { roleNames, type StaffRoleRow, type StaffRolesPolicy } from "./staffRolesApi";

/** The area each built-in role runs; a role this list does not name (for example one left over from before the fixed-role upgrade) falls under "Other roles". */
const ROLE_AREAS: Record<string, string> = {
  space_manager: "space", inventory_manager: "lending", handover: "lending", machine_manager: "machines",
  technician: "machines", event_manager: "events", booking_manager: "bookings", shop_manager: "shop",
};
const AREA_ORDER = ["space", "lending", "machines", "events", "bookings", "shop", "other"] as const;
type StaffArea = (typeof AREA_ORDER)[number];
const AREA_LABELS: Record<StaffArea, string> = {
  space: t`Whole space`, lending: t`Inventory`, machines: t`Machines`, events: t`Events`, bookings: t`Rooms and bookings`,
  shop: t`Shop`, other: t`Other roles`,
};

export type StaffRoleFilter = { role: string; grouped: boolean };

/** PE3: only the people holding one role. Applied to the page the server sent. */
export function filterStaffRows(rows: StaffRoleRow[], role: string) {
  return role ? rows.filter(row => row.roles.includes(role)) : rows;
}

/** PE3: staff grouped by the area their roles run; a person with roles in two areas appears in both. */
export function groupStaffRows(rows: StaffRoleRow[]) {
  return AREA_ORDER.map(area => ({
    area, label: AREA_LABELS[area],
    rows: rows.filter(row => {
      const areas = row.roles.map(role => ROLE_AREAS[role] ?? "other");
      return areas.includes(area) || (area === "other" && !row.roles.length);
    }),
  })).filter(group => group.rows.length);
}

export function StaffRoleFilterBar({ policy, rows, value, onChange, partial }: {
  policy?: StaffRolesPolicy; rows: StaffRoleRow[]; value: StaffRoleFilter; onChange: (next: StaffRoleFilter) => void;
  /** More than one page of staff exists, so a filter only covers the page on screen. */
  partial: boolean;
}) {
  // Roles held by someone on screen plus the ones this viewer may grant, so the filter never offers an empty choice.
  const slugs = [...new Set([...rows.flatMap(row => row.roles), ...(policy?.grantable_roles ?? []).map(role => role.slug), value.role].filter(Boolean))];
  return <div className="flex min-w-0 flex-wrap items-end gap-3">
    {slugs.length ? <label className="grid min-w-0 gap-1 text-sm">{t`Role`}
      <select className="desk-input max-w-full" value={value.role} onChange={event => onChange({ ...value, role: event.target.value })}>
        <option value="">{t`Every role`}</option>
        {slugs.map(slug => <option key={slug} value={slug}>{roleNames(policy, [slug])}</option>)}
      </select></label> : null}
    <label className="flex min-h-11 items-center gap-3 text-sm">
      <input type="checkbox" className="h-5 w-5 accent-accent" checked={value.grouped} onChange={event => onChange({ ...value, grouped: event.target.checked })} />
      {t`Group by area`}</label>
    {partial && (value.role || value.grouped) ? <p className="text-sm text-muted">{t`Applies to the people on this page.`}</p> : null}
  </div>;
}
