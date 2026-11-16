import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defaults, resetShellMocks, space, user, wrap, queryClient } from "../../../e2e/fixtures/staffShellHarness";
import { StaffApp } from "./StaffApp";

const { session } = vi.hoisted(() => ({ session: vi.fn() }));
vi.mock("./useConsoleSession", () => ({ useConsoleSession: session }));
vi.mock("./PlatformSignInPanel", () => ({ PlatformSignInPanel: () => <form><label>Username<input /></label><label>Password<input /></label></form> }));
vi.mock("../auth/MfaFlow", () => ({ MfaFlow: () => <p>MFA challenge</p> }));
vi.mock("./ChangePasswordGate", () => ({ ChangePasswordGate: ({ onChanged }: { onChanged: () => void }) => <button onClick={onChanged}>Change password gate</button> }));
vi.mock("./RecoveryQuarantinePanel", () => ({ RecoveryQuarantinePanel: () => <p>Recovery quarantine</p> }));
function setup(overrides: Record<string, unknown> = {}, url = "/admin/inventory") {
  const props = defaults(); const client = queryClient();
  const state = { ...props, user: user({ is_superuser: true }), restoring: false, recovery: { data: null },
    makerspaces: { data: props.makerspaces, isLoading: false }, consoleMakerspaces: props.makerspaces, selected: 1,
    tenant: { bootstrap: { makerspace: { name: "Community Lab" } } }, queryClient: client, setUser: vi.fn(),
    chooseMakerspace: vi.fn(), login: { mutate: vi.fn() }, ...overrides };
  session.mockReturnValue(state); wrap(<StaffApp />, url, client); return state;
}
const noShell = () => expect(document.querySelector("[data-app-shell]")).toBeNull();
beforeEach(resetShellMocks);
describe("StaffApp gate order", () => {
  it("S1 restoring wins before all other gates and shows no shell", () => { setup({ restoring: true }); expect(screen.getByText("Restoring session...")).toBeInTheDocument(); noShell(); });
  it("S2 MFA renders alone before login", () => { setup({ user: null, mfaChallenge: { challenge: "c" } }); expect(screen.getByText("MFA challenge")).toBeInTheDocument(); noShell(); });
  it("S3 the signed-out platform console gets Username/Password without shell", () => { setup({ user: null, platform: true }); expect(screen.getByLabelText("Username")).toBeInTheDocument(); expect(screen.getByLabelText("Password")).toBeInTheDocument(); noShell(); });
  it("S4 password-change gate invalidates protected makerspaces and clears must-change flag", () => {
    const client = queryClient(); const invalidation = vi.spyOn(client, "invalidateQueries");
    const state = setup({ queryClient: client, user: user({ must_change_password: true }) });
    noShell(); fireEvent.click(screen.getByText("Change password gate"));
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ["staff", "makerspaces"] });
    expect(state.setUser).toHaveBeenCalledWith(expect.objectContaining({ must_change_password: false }));
  });
  it("S5 superadmin quarantine wins before workspace loading", () => { setup({ recovery: { data: { mode: "quarantined" } }, makerspaces: { isLoading: true } }); expect(screen.getByText("Recovery quarantine")).toBeInTheDocument(); noShell(); });
  it("S6 single-tenant loading checks access before entering shell", () => { setup({ singleTenantLocked: true, makerspaces: { isLoading: true } }); expect(screen.getByText("Checking makerspace access...")).toBeInTheDocument(); noShell(); });
  it.each(["/admin/inventory", "/admin/platform-dashboard"])("S7 single-tenant missing workspace denies %s", url => { setup({ singleTenantLocked: true, activeMakerspace: undefined }, url); expect(screen.getByRole("heading", { name: /You do not have access/ })).toBeInTheDocument(); noShell(); });
  it.each([
    { routeMakerspaceSlug: "b", makerspaces: { isLoading: true } },
    { routeMakerspaceSlug: "b", routeMakerspace: space(2, "b") },
  ])("S8 opens route workspace until list and selection synchronize (%j)", overrides => { setup(overrides, "/m/b/admin/inventory"); expect(screen.getByText("Opening makerspace...")).toBeInTheDocument(); noShell(); });
  it("S9 restores selected workspace while list loads", () => { setup({ makerspaces: { isLoading: true } }); expect(screen.getByText("Opening makerspace...")).toBeInTheDocument(); noShell(); });
  it.each([null, 999])("S10 picker remains outside shell for invalid selection %s", selected => { setup({ selected, activeMakerspace: undefined }); expect(screen.getByRole("heading", { name: "Choose a makerspace to operate" })).toBeInTheDocument(); noShell(); });
  it.each([null, 999])("S11 platform global route bypasses picker for selection %s", selected => { setup({ selected, activeMakerspace: undefined }, "/admin/platform-dashboard"); expect(screen.getByTestId("tab")).toHaveTextContent("platform-dashboard"); expect(document.querySelector("[data-app-shell]")).toBeInTheDocument(); });
  it.each([true, false])("S12 Organizations is global for superadmin=%s", is_superuser => { setup({ selected: null, activeMakerspace: undefined, user: user({ is_superuser, makerspaces: [], has_elevated_authority: true }) }, "/admin/organizations"); expect(screen.getByTestId("tab")).toHaveTextContent("organizations"); });
  it("W8 Switch makerspace forwards null through chooseMakerspace", () => {
    const state = setup(); fireEvent.click(screen.getByRole("button", { name: /Community Lab.*Super Admin/ }));
    fireEvent.click(screen.getByRole("button", { name: "Switch makerspace" })); expect(state.chooseMakerspace).toHaveBeenCalledWith(null);
  });
  it("W41 user-menu Sign out forwards the real session signOut", () => {
    const state = setup(); fireEvent.click(screen.getAllByRole("button", { name: /manager Super Admin/ })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Sign out" })); expect(state.signOut).toHaveBeenCalledOnce();
  });
});
