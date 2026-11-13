import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { StaffShell } from "../../src/features/staff/StaffShell";
import { getStaffAccess } from "../../src/features/staff/staffAccess";
import { tabFromStaffPath } from "../../src/features/staff/staffTabs";
import { PageHeader } from "../../src/components/ui";
import { MemberPortalTabs, useMemberTab } from "../../src/features/members/MemberPortalTabs";
import { setAccessToken } from "../../src/lib/api";
import type { Makerspace } from "../../src/features/staff/panels/shared";
import type { StaffAuthUser } from "../../src/lib/api";
import "../../src/index.css";
window.fetch = async () => new Response(JSON.stringify({ count: 3, results: [] }), { headers: { "Content-Type": "application/json" } });
setAccessToken("fixture");
const actor = new URLSearchParams(location.search).get("actor") ?? "superadmin";
const actions = actor === "handout" ? ["issue_request", "return_request", "upload_evidence", "issue_direct_loan", "record_payment", "collect_service_request"] : ["manage_machines"];
const isSuperadmin = actor === "superadmin";
const space = { id: 1, name: "Community Lab", slug: "lab" } as Makerspace;
const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const modules = ["membership", "request_workflow", "bookings", "events"];
function Fixture() {
  const location = useLocation(); const access = getStaffAccess(actions, isSuperadmin, false, actor === "machine");
  const active = useMemberTab(modules);
  if (actor === "member") return <MemberPortalTabs modules={modules} active={active} user={{ name: "Member", menu: [], onSignOut: () => {} }}><PageHeader title="Member access" /></MemberPortalTabs>;
  return <StaffShell activeMakerspace={space} allowedTabs={access.allowedTabs} activeTab={tabFromStaffPath(location.pathname, false)}
    actions={actions} handoutOnly={access.handoutOnly} guestOnly={false} singleTenantLocked={false} isSuperadmin={isSuperadmin}
    user={{ username: "casey", makerspaces: [] } as unknown as StaffAuthUser} roleName={isSuperadmin ? "Super Admin" : "Operator"}
    makerspaces={[space, { ...space, id: 2, name: "Second Lab", slug: "second" }]} setSelected={() => {}} setTab={() => {}} signOut={async () => {}}>
    <PageHeader title="Settings workspace" /><p>Shell contract fixture</p>
  </StaffShell>;
}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[actor === "member" ? "/m/lab/member/overview" : "/m/lab/admin/settings"]}><Fixture /></MemoryRouter></QueryClientProvider>);
