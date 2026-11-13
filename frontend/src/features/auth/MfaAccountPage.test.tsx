import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MfaAccountPage } from "./MfaAccountPage";
const { request, clear, copy } = vi.hoisted(() => ({ request: vi.fn(), clear: vi.fn(), copy: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest: request, clearAccessToken: clear, setAccessToken: vi.fn(), refreshAccessToken: () => Promise.resolve(true), getAccessToken: () => null }));
// S-D: the page also lists passkeys and remembered devices; give those routes their real shapes.
const respond = (status: object) => (url: string) => Promise.resolve(url === "/auth/mfa" ? status
  : url === "/auth/passkeys" ? { passkeys: [], passkeys_allowed: true, rp_id: "localhost" } : url === "/auth/devices" || url === "/auth/social/providers" ? [] : { recovery_codes: ["ABCD-EFGH", "IJKL-MNOP"] });
beforeEach(() => {
  request.mockReset(); clear.mockReset(); copy.mockReset(); copy.mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: copy } });
  request.mockImplementation(respond({ enabled: true, required: false }));
});
it("regenerates, copies and acknowledges existing recovery codes without another API mutation", async () => {
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><MfaAccountPage /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText("Authenticator on")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Confirm your current password"), { target: { value: "current-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Regenerate recovery codes" }));
  expect(await screen.findByRole("heading", { name: "Save your recovery codes" })).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith("/auth/mfa/recovery", { method: "POST", body: JSON.stringify({ password: "current-password" }) });
  expect(clear).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Copy all" }));
  await waitFor(() => expect(copy).toHaveBeenCalledWith("ABCD-EFGH\nIJKL-MNOP"));
  const createUrl = vi.fn(() => "blob:recovery-codes");
  const revokeUrl = vi.fn();
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createUrl });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeUrl });
  const download = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  fireEvent.click(screen.getByRole("button", { name: "Download .txt" }));
  expect(createUrl).toHaveBeenCalledWith(expect.any(Blob));
  expect((download.mock.instances[0] as HTMLAnchorElement).download).toBe("space-works-recovery-codes.txt");
  expect(revokeUrl).toHaveBeenCalledWith("blob:recovery-codes");
  download.mockRestore();
  fireEvent.click(screen.getByRole("button", { name: "I've saved my codes" }));
  expect(screen.queryByRole("list", { name: "Recovery codes" })).toBeNull();
  expect(screen.getByText("Your recovery codes are saved. Sign in again to continue.")).toBeInTheDocument();
  expect(request.mock.calls.filter(call => call[1]?.method === "POST")).toHaveLength(1);
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
});

it("keeps disabling unavailable when two-step sign-in is required", async () => {
  request.mockImplementation(respond({ enabled: true, required: true }));
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><MfaAccountPage /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText("Authenticator on")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /disable mfa/i })).toBeNull();
  expect(screen.getByRole("button", { name: "Regenerate recovery codes" })).toBeDisabled();
  expect(request.mock.calls.filter(call => call[1]?.method === "POST")).toHaveLength(0);
});

describe("Deployment MFA availability", () => {
  const mount = () => render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><MfaAccountPage /></MemoryRouter></QueryClientProvider>);

  it.each([false, true])("hides enrollment and regeneration while off (enrolled=%s)", async (enabled) => {
    request.mockImplementation(respond({ available: false, enabled, required: false }));
    mount();
    expect(await screen.findByText("Two-step sign-in is turned off on this deployment.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enroll authenticator" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Regenerate recovery codes" })).not.toBeInTheDocument();
    expect(Boolean(screen.queryByRole("button", { name: /disable mfa/i }))).toBe(enabled);
  });

  it("offers enrollment when MFA is available", async () => {
    request.mockImplementation(respond({ available: true, enabled: false, required: false }));
    mount();
    expect(await screen.findByRole("button", { name: "Enroll authenticator" })).toBeInTheDocument();
    expect(screen.queryByText("Two-step sign-in is turned off on this deployment.")).not.toBeInTheDocument();
  });
});
