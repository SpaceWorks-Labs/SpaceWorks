import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../lib/api";
import { WalletCredentialsCard } from "./WalletCredentialsCard";
import { walletSettingsSections } from "./walletSettingsSection";

vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest: vi.fn() }));

const show = (scope: Parameters<typeof WalletCredentialsCard>[0]["scope"]) =>
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><WalletCredentialsCard scope={scope} /></QueryClientProvider>);

describe("WalletCredentialsCard", () => {
  beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

  it("says when a space signs with the platform's credentials and never shows secrets", async () => {
    vi.mocked(staffRequest).mockResolvedValue({
      apple: { configured: false }, google: { configured: true, issuer_id: "3388", class_prefix: "space", fingerprint: "abcdef0123456789abcdef" },
      effective: { apple: "platform", google: "space" },
    });
    show({ kind: "space", makerspaceId: 3 });
    expect(await screen.findByText("Using the platform's credentials.")).toBeVisible();
    expect(screen.getByText("Using this space's credentials.")).toBeVisible();
    expect(screen.getByText(/Issuer 3388/)).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/wallet-credentials");
  });

  it("saves Google credentials from the key file and removes a platform group", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ apple: { configured: true, pass_type_id: "pass.org.x", team_id: "T1", expires_soon: true }, google: { configured: false } });
    show({ kind: "platform" });
    expect(await screen.findByText(/expires soon/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/wallet-credentials", { method: "PATCH", body: JSON.stringify({ clear_apple: true }) }));
    fireEvent.click(screen.getByRole("button", { name: "Add credentials" }));
    fireEvent.change(screen.getByLabelText("Issuer ID"), { target: { value: "3388" } });
    const file = new File(['{"type":"service_account"}'], "key.json", { type: "application/json" });
    Object.defineProperty(file, "text", { value: () => Promise.resolve('{"type":"service_account"}') });
    fireEvent.change(screen.getByLabelText("Service-account key file (JSON)"), { target: { files: [file] } });
    await screen.findByText(/Key file loaded/);
    fireEvent.click(screen.getByRole("button", { name: "Save Google credentials" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/wallet-credentials", { method: "PATCH",
      body: JSON.stringify({ google_issuer_id: "3388", google_class_prefix: "", google_service_account: '{"type":"service_account"}' }) }));
  });

  it("keeps a reissue notice up after a save changes the Apple pass type", async () => {
    const apple = { configured: true, pass_type_id: "pass.org.new", team_id: "T1" };
    vi.mocked(staffRequest)
      .mockResolvedValueOnce({ apple: { ...apple, pass_type_id: "pass.org.old" }, google: { configured: false } })
      .mockResolvedValueOnce({ apple, google: { configured: false }, reissue_needed: true })
      .mockResolvedValueOnce({ apple, google: { configured: false }, reissue_needed: false });
    show({ kind: "space", makerspaceId: 3 });
    fireEvent.click(await screen.findByRole("button", { name: "Replace credentials" }));
    expect(screen.getByText(/Changing the Pass Type ID starts a new pass type/)).toBeVisible();
    expect(screen.queryByText("Your Apple pass type changed.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(await screen.findByText("Your Apple pass type changed.")).toBeVisible();
    expect(screen.getByText(/ask holders to re-add them from My passes/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(3));
    expect(screen.getByText("Your Apple pass type changed.")).toBeVisible();
  });
});

describe("walletSettingsSections (ID-11)", () => {
  const space = (features: string[]) => ({ id: 3, enabled_modules: ["membership", "events"], enabled_features: features });
  it("shows the wallet credentials for either wallet switch, to the Space Manager only", () => {
    expect(walletSettingsSections(space(["events.wallet_passes"]), true).map(section => section.id)).toEqual(["wallet"]);
    expect(walletSettingsSections(space(["membership.wallet_passes"]), true).map(section => section.id)).toEqual(["wallet"]);
    expect(walletSettingsSections(space(["membership.wallet_passes", "events.wallet_passes"]), true)).toHaveLength(1);
    expect(walletSettingsSections(space([]), true)).toEqual([]);
    expect(walletSettingsSections(space(["events.wallet_passes"]), false)).toEqual([]);
  });

  it("is absent when the switch's module is off", () => {
    expect(walletSettingsSections({ id: 3, enabled_modules: ["membership"], enabled_features: ["events.wallet_passes"] }, true)).toEqual([]);
  });
});
