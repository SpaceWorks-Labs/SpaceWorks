import { configure, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
const QC = ({ children }: { children: ReactNode }) => <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../../AppRoutes";

const { publicV1Request, tenant, staffApp } = vi.hoisted(() => ({
  publicV1Request: vi.fn(), staffApp: vi.fn(), tenant: { mode: "central", slug: "" },
}));
vi.mock("../../lib/api", () => ({ publicV1Request }));
vi.mock("../../lib/tenant", () => ({ useTenant: () => tenant }));
vi.mock("../staff/StaffApp", () => ({ StaffApp: () => { staffApp(); return <div>Staff shell</div>; } }));
vi.mock("../staff/PlatformApps", () => ({ SuperadminPage: () => null }));
vi.mock("../public/MakerspacePage", () => ({ MakerspacePage: () => null }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: vi.fn() }));
vi.mock("../kiosk/PublicDeskKioskPage", () => ({ PublicDeskKioskPage: () => null }));
vi.mock("../kiosk/ScannerPage", () => ({ ScannerPage: () => null }));
vi.mock("../NotFoundPage", () => ({ NotFoundPage: () => <h1>Page not found</h1> }));

// AppRoutes lazy-loads the recovery page; under a loaded full-suite shard its first chunk can take over
// the default 1 s, so the page was still on its loading status when findBy gave up.
configure({ asyncUtilTimeout: 5000 });
function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}</output>;
}
function renderPage(path: string, mode: "central" | "single" = "central") {
  tenant.mode = mode;
  tenant.slug = mode === "single" ? "alpha" : "";
  return render(<MemoryRouter initialEntries={[path]}>
    <AppRoutes mode={mode} landing={null} /><LocationProbe />
  </MemoryRouter>, { wrapper: QC });
}
function fillConfirmation() {
  fireEvent.change(screen.getByLabelText("Username or email"), { target: { value: "operator.alpha" } });
  fireEvent.change(screen.getByLabelText("Six-digit code"), { target: { value: "123456" } });
  fireEvent.change(screen.getByLabelText("New password"), { target: { value: "Recovery-password-419!" } });
  fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "Recovery-password-419!" } });
}
describe("signed-out console password recovery", () => {
  beforeEach(() => { publicV1Request.mockReset(); staffApp.mockClear(); });

  it.each([
    ["central", "/admin/reset-password?context=platform", { context: "platform" }, "/admin?context=platform"],
    ["single", "/admin/reset-password?context=platform", { context: "platform" }, "/admin?context=platform"],
  ] as const)("confirms %s %s with the platform context without mounting a session", async (mode, path, context, signIn) => {
    publicV1Request.mockResolvedValueOnce({ detail: "Password updated." });
    renderPage(path, mode);
    expect(await screen.findByRole("heading", { name: "Enter your recovery code" })).toBeInTheDocument();
    expect(staffApp).not.toHaveBeenCalled();
    fillConfirmation();
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));
    expect(await screen.findByRole("heading", { name: "Password updated" })).toBeInTheDocument();
    expect(JSON.parse(publicV1Request.mock.calls[0][1].body)).toEqual({
      email: "operator.alpha", code: "123456", new_password: "Recovery-password-419!", ...context,
    });
    expect(publicV1Request.mock.calls[0][1].headers).toEqual({ Authorization: "" });
    expect(screen.getByRole("link", { name: "Go to sign in" })).toHaveAttribute("href", signIn);
    expect(screen.getByText(/Authenticator verification is still required/)).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent(path);
    expect(screen.getByTestId("location")).not.toHaveTextContent("operator.alpha");
  });

  it.each([
    ["central", "/m/alpha/admin/reset-password"],
    ["single", "/admin/reset-password"],
    ["central", "/m/alpha/admin/reset-password?context=platform"],
  ] as const)("a space console (%s %s) recovers the person's account by email (release 2)", async (mode, path) => {
    publicV1Request.mockResolvedValueOnce({ detail: "If the account is eligible, a recovery request has been accepted." });
    renderPage(path, mode);
    await screen.findByRole("heading", { name: "Reset password" });
    expect(staffApp).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "operator@alpha.test" } });
    fireEvent.click(screen.getByRole("button", { name: "Request recovery code" }));
    expect(await screen.findByRole("heading", { name: "Enter your recovery code" })).toBeInTheDocument();
    expect(JSON.parse(publicV1Request.mock.calls[0][1].body)).toEqual({ email: "operator@alpha.test" });
  });

  it("requests a platform code with a username identifier", async () => {
    publicV1Request.mockResolvedValueOnce({ detail: "If the account is eligible, a recovery request has been accepted." });
    renderPage("/admin/reset-password?context=platform&step=request");
    await screen.findByRole("heading", { name: "Reset password" });
    fireEvent.change(screen.getByLabelText("Username or email"), { target: { value: "operator.alpha" } });
    fireEvent.click(screen.getByRole("button", { name: "Request recovery code" }));
    expect(await screen.findByRole("heading", { name: "Enter your recovery code" })).toBeInTheDocument();
    expect(JSON.parse(publicV1Request.mock.calls[0][1].body)).toEqual({ email: "operator.alpha", context: "platform" });
  });

  it("does not use legacy bearer parameters on a space recovery page", async () => {
    renderPage("/m/alpha/admin/reset-password?uid=staff-id&token=old-token");
    expect(await screen.findByRole("heading", { name: "Reset password" })).toBeInTheDocument();
    expect(publicV1Request).not.toHaveBeenCalled();
    expect(screen.queryByRole("heading", { name: "Set a new password" })).not.toBeInTheDocument();
  });

  it("refuses a different tenant's prefixed route on a single tenant frontend", async () => {
    renderPage("/m/beta/admin/reset-password", "single");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(publicV1Request).not.toHaveBeenCalled();
  });
});
