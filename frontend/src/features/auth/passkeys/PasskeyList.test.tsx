import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../../test/axe";
import { listPasskeys, registerPasskey, removePasskey, renamePasskey } from "./passkeyApi";
import { PasskeyList } from "./PasskeyList";

vi.mock("./passkeyApi", () => ({ listPasskeys: vi.fn(), registerPasskey: vi.fn(), removePasskey: vi.fn(), renamePasskey: vi.fn() }));
const support = vi.hoisted(() => ({ passkeys: true }));
vi.mock("./webauthn", async original => ({
  ...await original<typeof import("./webauthn")>(), passkeysSupported: () => support.passkeys,
}));
const tokens = vi.hoisted(() => ({ setAccessToken: vi.fn(), clearAccessToken: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...await original<typeof import("../../../lib/api")>(), ...tokens }));

const list = vi.mocked(listPasskeys);
const register = vi.mocked(registerPasskey);
const remove = vi.mocked(removePasskey);
const rename = vi.mocked(renamePasskey);
const passkey = (overrides = {}) => ({ id: 4, name: "Work laptop", created_at: "2026-10-01T10:00:00Z", last_used_at: "2026-11-02T10:00:00Z",
  backed_up: true, usable_here: true, rp_id: "spaceworks.test", ...overrides });
const LIST = { passkeys: [passkey(), passkey({ id: 5, name: "", last_used_at: null, backed_up: false })], passkeys_allowed: true };

function mount(onSignedOut = vi.fn()) {
  const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <PasskeyList onRecoveryCodes={vi.fn()} onSignedOut={onSignedOut} />
  </QueryClientProvider>);
  return view;
}

beforeEach(() => { [list, register, remove, rename, tokens.setAccessToken, tokens.clearAccessToken].forEach(mock => mock.mockReset()); support.passkeys = true; });

describe("PasskeyList", () => {
  it("lists passkeys with when they were added and last used", async () => {
    list.mockResolvedValue(LIST as never);
    const { container } = mount();
    expect(await screen.findByText("Work laptop")).toBeInTheDocument();
    expect(screen.getByText(/Last used/)).toBeInTheDocument();
    expect(screen.getByText(/Synced across your devices/)).toBeInTheDocument();
    expect(screen.getByText("Passkey")).toBeInTheDocument();
    expect(screen.getByText(/Not used yet/)).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("renames a passkey", async () => {
    list.mockResolvedValue(LIST as never);
    rename.mockResolvedValue(passkey({ name: "Desk key" }) as never);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Rename Work laptop" }));
    fireEvent.change(screen.getByLabelText("Passkey name"), { target: { value: " Desk key " } });
    fireEvent.click(screen.getByRole("button", { name: "Save name" }));
    await waitFor(() => expect(rename).toHaveBeenCalledWith(4, "Desk key"));
    expect(await screen.findByText("Passkey renamed.")).toBeInTheDocument();
  });

  it("removes a passkey after confirming and keeps this browser's new session", async () => {
    list.mockResolvedValue(LIST as never);
    remove.mockResolvedValue({ access: "fresh", signed_out: false } as never);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Remove Work laptop" }));
    expect(remove).not.toHaveBeenCalled();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Remove passkey" }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(4));
    expect(tokens.setAccessToken).toHaveBeenCalledWith("fresh");
    expect(await screen.findByText("Passkey removed. Other devices were signed out.")).toBeInTheDocument();
  });

  it("signs this browser out when the removed passkey was its only proof", async () => {
    list.mockResolvedValue(LIST as never);
    remove.mockResolvedValue({ signed_out: true } as never);
    const onSignedOut = vi.fn();
    mount(onSignedOut);
    fireEvent.click(await screen.findByRole("button", { name: "Remove Work laptop" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Remove passkey" }));
    await waitFor(() => expect(onSignedOut).toHaveBeenCalled());
    expect(tokens.clearAccessToken).toHaveBeenCalled();
  });

  it("adds a passkey, and refuses last_factor in plain words", async () => {
    list.mockResolvedValue({ passkeys: [], passkeys_allowed: true } as never);
    register.mockResolvedValue({ access: "after-add" } as never);
    mount();
    expect(await screen.findByText(/No passkeys yet/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add a passkey" }));
    await waitFor(() => expect(tokens.setAccessToken).toHaveBeenCalledWith("after-add"));
  });

  it("hides Add when passkeys are off for the account or the browser cannot create one", async () => {
    list.mockResolvedValue({ ...LIST, passkeys_allowed: false } as never);
    mount();
    expect(await screen.findByText(/Passkeys are turned off for your account/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add a passkey" })).not.toBeInTheDocument();
  });

  it("explains a browser that cannot create passkeys", async () => {
    support.passkeys = false;
    list.mockResolvedValue(LIST as never);
    mount();
    expect(await screen.findByText(/This browser can't create passkeys/)).toBeInTheDocument();
  });
});
