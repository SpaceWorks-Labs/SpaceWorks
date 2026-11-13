import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { StaffAuthUser } from "../../lib/api";
import { StaffTabContent } from "./StaffTabContent";
import { getStaffAccess, TAB_LABELS } from "./staffAccess";
import { staffTabPath, tabFromStaffPath } from "./staffTabs";

const makerspace = {
  id: 19,
  name: "North workshop",
  public_code: "NORTH",
  slug: "north",
  telegram_group_chat_id: "",
  frontend_domain: null,
  hidden_from_central_directory: false,
};

const user: StaffAuthUser = {
  username: "owner",
  email_verified: true,
  role: "staff",
  is_superuser: false,
  must_change_password: false,
  makerspaces: [],
};

describe("organization analytics tab", () => {
  it("is registered with a stable route and Insights label", () => {
    expect(TAB_LABELS["organization-analytics"]).toBe("Organization analytics");
    expect(staffTabPath("organization-analytics", false)).toBe("/admin/organization-analytics");
    expect(tabFromStaffPath("/admin/organization-analytics", false))
      .toBe("organization-analytics");
  });

  // Skipped 0.12.0: TAB_GROUPS removed (open item B6); kept per decision 244.
  it.skip("sits in the Insights group", () => {
    const TAB_GROUPS: { label: string; tabs: string[] }[] = [];
    expect(TAB_GROUPS.find((group) => group.label === "Insights")?.tabs)
      .toContain("organization-analytics");
  });

  it("does not advertise or mount the targetless panel when single-tenant locked", () => {
    expect(getStaffAccess(["view_audit"], false, true).allowedTabs)
      .not.toContain("organization-analytics");

    render(
      <QueryClientProvider client={new QueryClient()}>
      <StaffTabContent
        activeMakerspace={makerspace}
        activeTab="organization-analytics"
        guestOnly={false}
        makerspaces={[makerspace]}
        isSuperadmin={false}
        currentUser={user}
        onAuthRefresh={() => {}}
        printingOnly={false}
        canChooseToBuyKind={false}
        canEditInventory={false}
        canIssueDirectLoan={false}
        canCollectServiceRequests={false}
        canUseToBuy={false}
        canManageQr={false}
        canManageMakerspace={false}
        canUseMemberCards={false}
        canManageMachines={false}
        isMachineOnly={false}
        canConfigureMachineTypes={false}
        canManageEvents={false}
        canManageBookings={false}
        canSeeHardware={false}
        canSeePrinting={false}
        canViewAudit
        singleTenantLocked
      />
      </QueryClientProvider>,
    );

    expect(screen.queryByRole("heading", { name: "Organization analytics" }))
      .not.toBeInTheDocument();
  });
});
