import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AdminMembership } from "../../generated/api";
import { MemberRow } from "./MemberRow";
import type { MembershipRoles } from "./panels/roleSets";
import type { StaffRole } from "./panels/rolesApi";

const memberRole: StaffRole = { id: 1, makerspace_id: 3, name: "Member", slug: "member", granted_actions: [], legacy_role: null,
  is_default: true, is_protected: true, combinable: false, exclusive: true, member_count: 1, created_at: "", updated_at: "" };

describe("member detail drawer", () => {
  it("keeps delegation in the drawer and preserves capability payloads", () => {
    const onCapability = vi.fn();
    const member = { id: 7, status: "active", user: { id: 9, username: "mira", display_name: "Mira", email: "mira@example.test" }, assigned_role: { id: 1, name: "Member" },
      role_ids: [1], roles: [{ id: 1, name: "Member", slug: "member" }], can_refer: false, can_verify: false, waiver_required: false } as AdminMembership & MembershipRoles;
    render(<QueryClientProvider client={new QueryClient()}><MemberRow makerspaceId={3} member={member} roles={[memberRole]} onAuthRefresh={vi.fn()}
      canManageMakerspace canViewFinance={false} canRecordPayment={false} membershipEnabled
      changingCapabilities={false} changingVerification={false} changingWitness={false}
      onCapability={onCapability} onVerify={vi.fn()} onWitness={vi.fn()} onRevoke={vi.fn()} onTerms={vi.fn()} /></QueryClientProvider>);
    expect(screen.queryByRole("checkbox", { name: "Can refer" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Mira"));
    expect(screen.getByRole("dialog")).toBeVisible();
    fireEvent.click(screen.getByRole("checkbox", { name: "Can refer" }));
    expect(onCapability).toHaveBeenCalledWith({ can_refer: true });
    // Fixed roles: the drawer edits the whole role set, starting from the member's current roles.
    fireEvent.click(screen.getByRole("button", { name: "Change roles" }));
    expect(screen.getByRole("checkbox", { name: "Member" })).toBeChecked();
  });
});
