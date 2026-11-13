import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api/errors";
import { MemberPortalTabs } from "../members/MemberPortalTabs";
import { StaffShell } from "../staff/StaffShell";
import type { Makerspace } from "../staff/panels/shared";
import { PausedTenantGate, publicTenantSlug } from "./PausedTenantGate";
import { GENERIC_PAUSE_REASON, PAUSED_TITLE } from "./PausedSpacePage";
import { READ_ONLY_LEAD } from "./platformNoticesApi";

const { staffRequest, publicV1Request } = vi.hoisted(() => ({ staffRequest: vi.fn(), publicV1Request: vi.fn() }));
vi.mock("../../lib/api/requests", async (importOriginal) => ({ ...await importOriginal<object>(), staffRequest }));
vi.mock("../../lib/api", async (importOriginal) => ({ ...await importOriginal<object>(), staffRequest, publicV1Request }));

const SUSPENDED = { id: 7, name: "North Lab", slug: "north-lab", state: "suspended", reason: GENERIC_PAUSE_REASON, since: "2026-11-01T00:00:00Z" };
const SPACE = { id: 7, name: "North Lab", slug: "north-lab", public_code: "NL" } as Makerspace;
const OTHER = { id: 8, name: "South Lab", slug: "south-lab", public_code: "SL" } as Makerspace;

function wrap(children: ReactNode, client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/north-lab/member"]}>{children}</MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); publicV1Request.mockReset(); window.localStorage.clear(); });

describe("paused spaces", () => {
  it("replaces the staff console with the paused page and offers a switch", async () => {
    staffRequest.mockResolvedValue({ announcements: [], spaces: [SUSPENDED] });
    const setSelected = vi.fn();
    wrap(<StaffShell activeMakerspace={SPACE} allowedTabs={[]} activeTab="dashboard" guestOnly={false} singleTenantLocked={false} handoutOnly={false}
      user={{ username: "ada", makerspaces: [] } as never} isSuperadmin={false} makerspaces={[SPACE, OTHER]} setSelected={setSelected}
      setTab={vi.fn()} signOut={vi.fn(async () => undefined)} actions={[]}><p>Console body</p></StaffShell>);
    expect(await screen.findByRole("heading", { name: PAUSED_TITLE })).toBeInTheDocument();
    expect(screen.getByText(GENERIC_PAUSE_REASON)).toBeInTheDocument();
    expect(screen.queryByText("Console body")).not.toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/platform-notices", {}, "person");
    fireEvent.click(screen.getByRole("button", { name: "Switch space" }));
    expect(setSelected).toHaveBeenCalledWith(null);
  });

  it("shows the paused page when the paused space is missing from the account's spaces", async () => {
    // A suspended space is unservable, so the console never lists it: match the route slug instead.
    staffRequest.mockResolvedValue({ announcements: [], spaces: [SUSPENDED] });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/m/north-lab/admin/dashboard"]}>
        <StaffShell allowedTabs={[]} activeTab="dashboard" guestOnly={false} singleTenantLocked={false} handoutOnly={false}
          user={{ username: "ada", makerspaces: [] } as never} isSuperadmin={false} makerspaces={[OTHER]} setSelected={vi.fn()}
          setTab={vi.fn()} signOut={vi.fn(async () => undefined)} actions={[]}><p>Console body</p></StaffShell>
      </MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole("heading", { name: PAUSED_TITLE })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Switch space" })).toBeInTheDocument();
  });

  it("shows the paused page to staff whose only space is paused", async () => {
    staffRequest.mockResolvedValue({ announcements: [], spaces: [SUSPENDED] });
    wrap(<StaffShell allowedTabs={[]} activeTab="dashboard" guestOnly={false} singleTenantLocked={false} handoutOnly={false}
      user={{ username: "ada", makerspaces: [] } as never} isSuperadmin={false} makerspaces={[]} setSelected={vi.fn()}
      setTab={vi.fn()} signOut={vi.fn(async () => undefined)} actions={[]}><p>Console body</p></StaffShell>);
    expect(await screen.findByRole("heading", { name: PAUSED_TITLE })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("opens a paused space for the superadmin with the warning banner instead of the paused page", async () => {
    staffRequest.mockResolvedValue({ announcements: [], spaces: [{ ...SUSPENDED, reason: "Private reason" }] });
    wrap(<StaffShell activeMakerspace={SPACE} allowedTabs={[]} activeTab="dashboard" guestOnly={false} singleTenantLocked={false} handoutOnly={false}
      user={{ username: "root", makerspaces: [] } as never} isSuperadmin makerspaces={[SPACE]} setSelected={vi.fn()}
      setTab={vi.fn()} signOut={vi.fn(async () => undefined)} actions={[]}><p>Console body</p></StaffShell>);
    expect(await screen.findByRole("alert")).toHaveTextContent("which is paused");
    expect(screen.getByText("Console body")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: PAUSED_TITLE })).not.toBeInTheDocument();
  });

  it("replaces the member area with the paused page", async () => {
    staffRequest.mockResolvedValue({ announcements: [], spaces: [SUSPENDED] });
    const onSignOut = vi.fn();
    wrap(<MemberPortalTabs modules={[]} active="overview" space={{ slug: "north-lab" }} user={{ name: "Ada", menu: [], onSignOut }}><p>Member body</p></MemberPortalTabs>);
    expect(await screen.findByRole("heading", { name: PAUSED_TITLE })).toBeInTheDocument();
    expect(screen.queryByText("Member body")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(onSignOut).toHaveBeenCalled();
  });

  it("shows the read-only banner inside the member area", async () => {
    staffRequest.mockResolvedValue({ announcements: [], spaces: [{ ...SUSPENDED, state: "read_only", reason: "Invoice overdue." }] });
    wrap(<MemberPortalTabs modules={[]} active="overview" space={{ id: 7, slug: "north-lab" }} user={{ name: "Ada", menu: [], onSignOut: vi.fn() }}><p>Member body</p></MemberPortalTabs>);
    expect(await screen.findByText(READ_ONLY_LEAD)).toBeInTheDocument();
    expect(screen.getByText("Member body")).toBeInTheDocument();
  });

  it("does not ask for notices while signed out", () => {
    wrap(<MemberPortalTabs modules={[]} active="overview" space={{ slug: "north-lab" }} user={{ name: "Not signed in", menu: [] }}><p>Member body</p></MemberPortalTabs>);
    expect(staffRequest).not.toHaveBeenCalled();
  });

  async function publicGate(state: "active" | "paused") {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    publicV1Request.mockResolvedValue({ state });
    await client.fetchQuery({ queryKey: ["tenant-bootstrap", "north-lab"], queryFn: () => Promise.reject(new StructuredApiError(404, { detail: "Not found." })) }).catch(() => undefined);
    wrap(<PausedTenantGate slug="north-lab"><p>Not found page</p></PausedTenantGate>, client);
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/public/makerspaces/north-lab/availability"));
  }

  it("shows the paused page on a public page whose bootstrap 404s for a paused space", async () => {
    await publicGate("paused");
    expect(await screen.findByRole("heading", { name: PAUSED_TITLE })).toBeInTheDocument();
    expect(screen.queryByText("Not found page")).not.toBeInTheDocument();
  });

  it("keeps the page's own not-found for an unknown space", async () => {
    await publicGate("active");
    expect(screen.getByText("Not found page")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: PAUSED_TITLE })).not.toBeInTheDocument();
  });

  it("never checks availability while the bootstrap succeeds", () => {
    wrap(<PausedTenantGate slug="north-lab"><p>Page</p></PausedTenantGate>);
    expect(publicV1Request).not.toHaveBeenCalled();
  });

  it("reads the tenant slug from public paths only", () => {
    expect(publicTenantSlug("/m/north-lab/events")).toBe("north-lab");
    expect(publicTenantSlug("/m/north-lab")).toBe("north-lab");
    expect(publicTenantSlug("/m/north-lab/admin/dashboard")).toBe("");
    expect(publicTenantSlug("/about")).toBe("");
  });
});
