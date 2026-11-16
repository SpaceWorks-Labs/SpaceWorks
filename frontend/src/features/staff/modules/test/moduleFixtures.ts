export const row = (key: string, label: string, extra: Record<string, unknown> = {}) => ({
  key, label, description: `${label} description.`, installed: false, core: false, available: true, requires: [], pulls_in: [],
  required_by: [], workflows: [], install_requires_superadmin: false, limits: [], lock_reason: null, ...extra });

export const modulesData = {
  groups: [
    { key: "inventory", label: "Inventory", description: "The loan spine.", always_on: true, installed_count: 2, module_count: 2, modules: [
      row("public_inventory", "Public inventory", { installed: true, core: true, lock_reason: "core" }),
      row("staff_admin", "Staff admin", { installed: true, core: true, lock_reason: "core" }) ] },
    { key: "bookings", label: "Bookings", description: "Resource booking.", always_on: false, installed_count: 0, module_count: 1, modules: [row("bookings", "Bookings")] },
    { key: "events", label: "Events", description: "Event scheduling.", always_on: false, installed_count: 2, module_count: 2, modules: [
      row("events", "Events", { installed: true, required_by: ["event_reimbursements"], workflows: ["event_registration"] }),
      row("event_reimbursements", "Event reimbursements", { installed: true, requires: ["events"] }) ] },
    { key: "notifications", label: "Notifications", description: "Channels.", always_on: false, installed_count: 0, module_count: 2, modules: [
      row("sms", "SMS", { install_requires_superadmin: true, lock_reason: "limit" }),
      row("whatsapp", "WhatsApp", { available: false, lock_reason: "not_shipped" }) ] },
  ],
  deployment: null, profiles: [],
};
export const rolesData = [
  { id: 1, makerspace_id: 7, name: "Space Manager", slug: "space_manager", granted_actions: ["manage_makerspace"] },
  { id: 2, makerspace_id: 7, name: "Inventory Manager", slug: "inventory_manager", granted_actions: ["view_inventory", "edit_inventory"] },
  { id: 3, makerspace_id: 7, name: "Front desk", slug: "front-desk", granted_actions: ["manage_bookings"] },
];
export const settingsData = { id: 7, enabled_features: ["membership.broadcasts"], enabled_modules: ["public_inventory", "staff_admin", "events", "event_reimbursements"] };
