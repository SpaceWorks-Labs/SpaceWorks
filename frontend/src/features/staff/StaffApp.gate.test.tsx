import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { notifyMfaEnrollmentRequired } from "../../lib/api/mfaEnrollment";
import { StaffApp } from "./StaffApp";

const { session } = vi.hoisted(() => ({ session: vi.fn() }));
vi.mock("./useConsoleSession", () => ({ useConsoleSession: session }));
vi.mock("./StaffWorkspace", () => ({ StaffWorkspace: ({ notice }: { notice?: React.ReactNode }) => <div><p>Workspace</p>{notice}</div> }));
vi.mock("./MakerspacePicker", () => ({ MakerspacePicker: ({ person }: { person?: boolean }) => <p>Pick a makerspace{person ? " (person)" : ""}</p> }));
vi.mock("./StaffAccessDenied", () => ({ StaffAccessDenied: () => <p>Tenant access denied</p> }));
vi.mock("../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Person sign-in</p> }));
vi.mock("./PlatformSignInPanel", () => ({ PlatformSignInPanel: () => <p>Platform sign-in</p> }));

const space = (id: number, slug: string) => ({ id, slug, name: slug.toUpperCase() });
const staffRole = (id: number, slug: string) => ({ makerspace: { id, slug, name: slug }, roles: [{ id: 1, slug: "inventory_manager", name: "Inventory Manager" }], actions: ["view_inventory"] });
const person = (overrides = {}) => ({ role: "requester", is_superuser: false, kind: "person", username: "pat", makerspaces: [],
  staff_roles: [staffRole(1, "a")], has_elevated_authority: true, mfa_enrolment_due: false, mfa_grace_ends_at: null, ...overrides });
const base = (overrides = {}) => ({ restoring: false, recovery: { data: null }, makerspaces: { data: [space(1, "a")], isLoading: false },
  consoleMakerspaces: [space(1, "a")], singleTenantLocked: false, selected: 1, activeMakerspace: space(1, "a"), tenant: {},
  platform: false, login: { mutate: vi.fn(), isPending: false }, signOut: vi.fn(), ...overrides });
const show = (url = "/m/a/admin/inventory") => render(<MemoryRouter initialEntries={[url]}><StaffApp /></MemoryRouter>);

describe("one account per person: the console gate", () => {
  beforeEach(() => { session.mockReturnValue(base({ user: person() })); });

  it("signed-out people use the one person sign-in; only the platform console has its own", () => {
    session.mockReturnValue(base({ user: null }));
    show(); expect(screen.getByText("Person sign-in")).toBeInTheDocument();
    session.mockReturnValue(base({ user: null, platform: true }));
    show("/admin?context=platform"); expect(screen.getByText("Platform sign-in")).toBeInTheDocument();
  });

  it("a person without staff roles or grants gets no console", () => {
    session.mockReturnValue(base({ user: person({ staff_roles: [], has_elevated_authority: false }), activeMakerspace: undefined }));
    show(); expect(screen.getByRole("heading", { name: "You don't have a staff role yet" })).toBeInTheDocument();
  });

  it("a person with roles in several spaces picks the space", () => {
    session.mockReturnValue(base({ user: person({ staff_roles: [staffRole(1, "a"), staffRole(2, "b")] }), selected: null, activeMakerspace: undefined, consoleMakerspaces: [space(1, "a"), space(2, "b")] }));
    show("/admin"); expect(screen.getByText("Pick a makerspace (person)")).toBeInTheDocument();
  });

  it("during the 3-day grace the console renders with the banner", () => {
    const ends = new Date(Date.now() + 86_400_000).toISOString();
    session.mockReturnValue(base({ user: person({ mfa_enrolment_due: true, mfa_grace_ends_at: ends }) }));
    show(); expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByText("Set up two-step sign-in")).toBeInTheDocument();
  });

  it("after the grace the console asks for enrolment, with a way back to member features", () => {
    session.mockReturnValue(base({ user: person({ mfa_enrolment_due: true, mfa_grace_ends_at: new Date(Date.now() - 1000).toISOString() }) }));
    show(); expect(screen.getByRole("heading", { name: "Set up two-step sign-in" })).toBeInTheDocument();
    expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Set up two-step sign-in" }).getAttribute("href")).toMatch(/^\/mfa\?return=/);
  });

  it("a mid-session mfa_enrollment_required refusal swaps the console in place", () => {
    show(); expect(screen.getByText("Workspace")).toBeInTheDocument();
    act(() => notifyMfaEnrollmentRequired());
    expect(screen.getByRole("heading", { name: "Set up two-step sign-in" })).toBeInTheDocument();
  });

  it("the superadmin keeps the platform dashboard without a tenant selection", () => {
    session.mockReturnValue(base({ user: { role: "superadmin", is_superuser: true, makerspaces: [], username: "root" }, selected: null, activeMakerspace: undefined, platform: true }));
    show("/admin/platform-dashboard?context=platform"); expect(screen.getByText("Workspace")).toBeInTheDocument();
    show("/admin/inventory?context=platform"); expect(screen.getAllByText("Pick a makerspace").length).toBeGreaterThan(0);
  });

  it("custom-domain tenants keep their access check", () => {
    session.mockReturnValue(base({ user: person({ staff_roles: [staffRole(9, "z")] }), singleTenantLocked: true, activeMakerspace: undefined, tenant: { makerspaceId: 1 } }));
    show("/admin/inventory"); expect(screen.getByText("Tenant access denied")).toBeInTheDocument();
  });
});
