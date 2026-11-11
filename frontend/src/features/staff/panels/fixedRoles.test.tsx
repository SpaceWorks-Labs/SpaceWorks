import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError, staffRequest } from "../../../lib/api";
import { expectNoA11yViolations } from "../../../test/axe";
import { RoleSetPicker } from "./RoleSetPicker";
import { MemberMachineTypes } from "./MemberMachineTypes";
import { MemberRolesControl } from "./MemberRolesControl";
import { assignableRoles } from "./roleSets";
import type { MemberMachineScope, StaffRole } from "./rolesApi";

vi.mock("../../../lib/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../lib/api")>(),
  staffRequest: vi.fn(),
}));

const roles: StaffRole[] = [
  ["space_manager", "Space Manager", ["manage_makerspace"]],
  ["member", "Member", []],
  ["event_manager", "Event Manager", ["manage_events"]],
  ["booking_manager", "Booking Manager", ["manage_bookings"]],
  ["machine_manager", "Machine Manager", ["manage_machines"]],
].map(([slug, name, granted_actions], index) => ({
  id: index + 1, makerspace_id: 7, slug: slug as string, name: name as string,
  granted_actions: granted_actions as string[], legacy_role: null,
  exclusive: ["space_manager", "member"].includes(slug as string),
  combinable: !["space_manager", "member"].includes(slug as string),
  is_default: true, is_protected: true, member_count: 0, created_at: "", updated_at: "",
}));

const scope: MemberMachineScope = {
  membership_id: 9, scoping_applies: true, machine_type_ids: [],
  available_machine_types: [
    { id: 21, name: "Printers", slug: "3d_printer", is_global: true },
    { id: 22, name: "Lasers", slug: "laser", is_global: false },
  ],
};

function Picker() {
  const [value, setValue] = useState([3]);
  return <RoleSetPicker roles={roles} value={value} onChange={setValue} />;
}

function mount(element: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const result = render(<QueryClientProvider client={client}>{element}</QueryClientProvider>);
  return { ...result, invalidate };
}

beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

describe("fixed membership roles", () => {
  it("combines staff roles and replaces the set when either exclusive role is checked", async () => {
    const { container } = render(<Picker />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Booking Manager" }));
    expect(screen.getByRole("checkbox", { name: "Event Manager" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Booking Manager" })).toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: /^Member$/ }));
    expect(screen.getByRole("checkbox", { name: "Event Manager" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Booking Manager" })).not.toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: "Machine Manager" }));
    expect(screen.getByRole("checkbox", { name: /^Member$/ })).not.toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: "Space Manager" }));
    expect(screen.getByRole("checkbox", { name: "Machine Manager" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Space Manager" })).toBeChecked();
    await expectNoA11yViolations(container);
  });

  it("only offers roles within the actor's ceiling, including the Space Manager restriction", () => {
    expect(assignableRoles(roles, ["manage_makerspace", "manage_events"], false).map((role) => role.slug))
      .toEqual(["member", "event_manager"]);
    expect(assignableRoles(roles, [], true)).toEqual(roles);
  });

  it("posts the complete set and prompts for types after first assigning Machine Manager", async () => {
    const refresh = vi.fn();
    vi.mocked(staffRequest).mockResolvedValueOnce({ role_ids: [3, 5], roles: [roles[2], roles[4]] }).mockResolvedValue(scope);
    const { invalidate } = mount(<MemberRolesControl msId={7} membershipId={9} membership={{ role_ids: [3], roles: [roles[2]] }} roles={roles} onAuthRefresh={refresh} />);
    fireEvent.click(screen.getByText("Change roles"));
    fireEvent.click(screen.getByRole("checkbox", { name: "Machine Manager" }));
    fireEvent.click(screen.getByRole("button", { name: "Save roles" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/memberships/9/role", {
      method: "PATCH", body: JSON.stringify({ role_ids: [3, 5] }),
    }));
    expect(await screen.findByRole("dialog", { name: "Machine types" })).toBeInTheDocument();
    expect(refresh).toHaveBeenCalled();
    for (const queryKey of [["members", 7], ["staff", "memberships", 7], ["member-machine-scope", 7], ["staff", "me"]]) {
      expect(invalidate).toHaveBeenCalledWith({ queryKey });
    }
  });
});

describe("per-person machine types", () => {
  it("replaces types only, supports All, and refreshes authority on save", async () => {
    const refresh = vi.fn();
    const close = vi.fn();
    vi.mocked(staffRequest).mockResolvedValue(scope);
    const { invalidate } = mount(<MemberMachineTypes msId={7} membershipId={9} onAuthRefresh={refresh} onClose={close} />);
    fireEvent.click(await screen.findByRole("checkbox", { name: "All machine types" }));
    fireEvent.click(screen.getByRole("checkbox", { name: /^Lasers$/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save machine types" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/memberships/9/machine-scope", {
      method: "PUT", body: JSON.stringify({ machine_type_ids: [21] }),
    }));
    await waitFor(() => expect(close).toHaveBeenCalled());
    expect(refresh).toHaveBeenCalled();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["staff", "me"] });
    for (const queryKey of [["machines"], ["machine-types"], ["dashboard"], ["procurement"]]) {
      expect(invalidate).toHaveBeenCalledWith({ queryKey });
    }
  });

  it("shows an honest non-applicable state without a save button", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ ...scope, scoping_applies: false });
    mount(<MemberMachineTypes msId={7} membershipId={9} onAuthRefresh={vi.fn()} onClose={vi.fn()} />);
    expect(await screen.findByText(/Save the Machine Manager role first/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save machine types" })).not.toBeInTheDocument();
  });

  it("keeps a 409 visible across scope refetch and does not close as if saved", async () => {
    const close = vi.fn();
    vi.mocked(staffRequest).mockResolvedValue(scope);
    mount(<MemberMachineTypes msId={7} membershipId={9} onAuthRefresh={vi.fn()} onClose={close} />);
    await screen.findByRole("checkbox", { name: /^Printers$/ });
    vi.mocked(staffRequest).mockRejectedValueOnce(new StructuredApiError(409, { detail: "Assign a role first." }));
    fireEvent.click(screen.getByRole("button", { name: "Save machine types" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Assign a role first.");
    expect(screen.getByRole("button", { name: "Save machine types" })).toBeDisabled();
    expect(close).not.toHaveBeenCalled();
  });
});
