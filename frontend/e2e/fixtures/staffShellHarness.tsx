import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { useContext, type ComponentProps, type ReactNode } from "react";
import { vi } from "vitest";
import { StaffWorkspace } from "../../src/features/staff/StaffWorkspace";
import { StaffListContext } from "../../src/features/staff/StaffListContext";
import type { StaffAuthUser } from "../../src/lib/api";
import type { Makerspace } from "../../src/features/staff/panels/shared";

const mocks = vi.hoisted(() => ({ request: vi.fn(), content: vi.fn(), checklist: vi.fn() }));
vi.mock("../../src/lib/api", async original => ({ ...await original<typeof import("../../src/lib/api")>(), staffRequest: mocks.request }));
vi.mock("../../src/features/staff/StaffTabContent", () => ({ StaffTabContent: (props: Record<string, unknown>) => {
  const context = useContext(StaffListContext);
  mocks.content(props, context);
  return <section data-testid="tab"><h1>{props.activeTab === "inventory" ? "Inventory" : String(props.activeTab)}</h1>{String(props.activeTab)}|{String(props.guestOnly)}{props.progress as ReactNode}</section>;
} }));
vi.mock("../../src/features/staff/SetupChecklist", () => ({ SetupChecklist: (props: unknown) => { mocks.checklist(props); return <p data-testid="checklist">Setup checklist</p>; } }));
vi.mock("../../src/components/ui/JobTray", () => ({ JobTray: ({ makerspaceId }: { makerspaceId: number }) => <p data-testid="jobs">Jobs {makerspaceId}</p> }));
export const space = (id = 1, slug = "lab", overrides: Partial<Makerspace> = {}) => ({
  id, slug, name: slug === "lab" ? "Community Lab" : slug.toUpperCase(), public_code: slug,
  telegram_group_chat_id: "", frontend_domain: null, hidden_from_central_directory: false, ...overrides,
} as Makerspace);
export const user = (overrides: Partial<StaffAuthUser> = {}) => ({
  username: "manager", is_superuser: false, role: "member", makerspaces: [{ id: 1, slug: "lab", role_name: "Space Manager", actions: ["manage_makerspace"] }], ...overrides,
} as StaffAuthUser);
export const manager = ["manage_makerspace", "view_inventory", "edit_inventory", "accept_request", "issue_request", "manage_qr", "manage_machines", "manage_events", "manage_bookings", "manage_members", "view_audit", "view_finance"];
export const handout = ["issue_request", "issue_direct_loan", "return_request", "upload_evidence", "collect_service_request", "record_payment"];
export const defaults = (): ComponentProps<typeof StaffWorkspace> => ({
  activeMakerspace: space(), actions: manager, isMachineOnly: false, canConfigureMachineTypes: true,
  guestOnly: false, isSuperadmin: false, makerspaces: [space(), space(2, "b")], onAuthRefresh: vi.fn(),
  selected: 1, setSelected: vi.fn(), setTab: vi.fn(), signOut: vi.fn().mockResolvedValue(undefined), singleTenantLocked: false, user: user(),
});
export function LocationProbe() { const location = useLocation(); return <output data-testid="location">{location.pathname}{location.search}{location.hash}</output>; }
export function queryClient() { return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } }); }
export function renderWorkspace(url = "/m/lab/admin/inventory", overrides: Partial<ComponentProps<typeof StaffWorkspace>> = {}, client = queryClient()) {
  const props = { ...defaults(), ...overrides };
  const view = render(<MemoryRouter initialEntries={[url]}><QueryClientProvider client={client}><StaffWorkspace {...props} /><LocationProbe /></QueryClientProvider></MemoryRouter>);
  return { ...view, props, client };
}
export function wrap(children: ReactNode, url: string, client = queryClient()) {
  return render(<MemoryRouter initialEntries={[url]}><QueryClientProvider client={client}>{children}<LocationProbe /></QueryClientProvider></MemoryRouter>);
}
export function resetShellMocks() {
  localStorage.clear(); vi.clearAllMocks();
  mocks.request.mockImplementation(async (path: string) => path.endsWith("/unread-count") ? { count: 3 } : { count: 0, results: [] });
}

export { mocks };
