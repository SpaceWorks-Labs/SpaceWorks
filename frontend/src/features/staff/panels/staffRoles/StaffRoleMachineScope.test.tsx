import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { MachineScopeChips } from "./MachineScopePicker";
import { StaffRoleFields, validRoleSet, type RoleDraft } from "./StaffRoleEditor";
import type { StaffRolesPolicy } from "./staffRolesApi";

const policy: StaffRolesPolicy = {
  grantable_roles: [{ slug: "space_manager", name: "Space Manager", combinable: false },
    { slug: "event_manager", name: "Event Manager", combinable: true }, { slug: "booking_manager", name: "Booking Manager", combinable: true },
    { slug: "machine_manager", name: "Machine Manager", combinable: true }, { slug: "technician", name: "Technician", combinable: true },
    { slug: "inventory_manager", name: "Inventory Manager", combinable: true }],
  can_manage_space_managers: true, email_invites_available: true,
  machine_types: [{ id: 3, name: "Laser cutter" }, { id: 4, name: "3D printer" }],
  machines: [{ id: 30, name: "Trotec Speedy", machine_type_id: 3 }, { id: 40, name: "Prusa MK4 #1", machine_type_id: 4 }, { id: 41, name: "Prusa MK4 #2", machine_type_id: 4 }],
  scoped_role_slugs: ["machine_manager", "technician"],
};

let latest: RoleDraft;
function Harness({ start = { roles: [], machine_type_ids: [], machine_ids: [] } }: { start?: RoleDraft }) {
  const [draft, setDraft] = useState<RoleDraft>(start);
  latest = draft;
  return <StaffRoleFields policy={policy} draft={draft} onChange={setDraft} />;
}
const box = (name: string | RegExp) => screen.getByRole("checkbox", { name });

describe("role editor: several roles and machine scope (decision 282)", () => {
  it("combines roles but keeps Space Manager alone", () => {
    render(<Harness />);
    fireEvent.click(box("Event Manager"));
    fireEvent.click(box("Booking Manager"));
    expect(latest.roles).toEqual(["event_manager", "booking_manager"]);
    expect(validRoleSet(policy, latest.roles)).toBe(true);
    fireEvent.click(box("Space Manager"));
    expect(latest.roles).toEqual(["space_manager"]);
    expect(validRoleSet(policy, ["space_manager", "event_manager"])).toBe(false);
  });

  it("offers machine types and single machines only for Machine Manager or Technician", () => {
    render(<Harness />);
    expect(screen.queryByRole("group", { name: "Laser cutter" })).toBeNull();
    fireEvent.click(box("Technician"));
    fireEvent.click(box("Inventory Manager"));
    fireEvent.click(box("Laser cutter"));
    fireEvent.click(box("Prusa MK4 #2"));
    expect(latest).toEqual({ roles: ["technician", "inventory_manager"], machine_type_ids: [3], machine_ids: [41] });
    expect(box(/Trotec Speedy/)).toBeChecked();
    expect(box(/Trotec Speedy/)).toBeDisabled();
    expect(screen.getByText("2 chosen")).toBeInTheDocument();
  });

  it("warns that nothing chosen means no machines, and clears the scope with the last scoped role", () => {
    render(<Harness start={{ roles: ["machine_manager"], machine_type_ids: [4], machine_ids: [30] }} />);
    fireEvent.click(box("3D printer"));
    fireEvent.click(box("Trotec Speedy"));
    expect(screen.getByText("Nothing chosen: this person looks after no machines.")).toBeInTheDocument();
    fireEvent.click(box("Laser cutter"));
    fireEvent.click(box("Event Manager"));
    fireEvent.click(box("Machine Manager"));
    expect(latest).toEqual({ roles: ["event_manager"], machine_type_ids: [], machine_ids: [] });
  });

  it("searches machines by name and types by name", () => {
    const many: StaffRolesPolicy = { ...policy, machines: [...policy.machines!, ...Array.from({ length: 8 }, (_, i) => ({ id: 100 + i, name: `Bench drill ${i}`, machine_type_id: 3 }))] };
    function Wide() {
      const [draft, setDraft] = useState<RoleDraft>({ roles: ["machine_manager"], machine_type_ids: [], machine_ids: [] });
      return <StaffRoleFields policy={many} draft={draft} onChange={setDraft} />;
    }
    render(<Wide />);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search machines and types" }), { target: { value: "prusa" } });
    expect(screen.queryByRole("checkbox", { name: "Laser cutter" })).toBeNull();
    expect(within(screen.getByRole("group", { name: "3D printer" })).getAllByRole("checkbox")).toHaveLength(3);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search machines and types" }), { target: { value: "zeppelin" } });
    expect(screen.getByText("No machines or types match.")).toBeInTheDocument();
  });

  it("shows scope chips: whole types first, then single machines", () => {
    render(<MachineScopeChips types={[{ id: 3, name: "Laser cutter" }]} machines={[{ id: 41, name: "Prusa MK4 #2" }]} />);
    const list = screen.getByRole("list", { name: "Machines they look after" });
    expect(within(list).getAllByRole("listitem").map(item => item.textContent)).toEqual(["All Laser cutter", "Prusa MK4 #2"]);
  });
});
