import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PlatformCredentialsPanel } from "./PlatformCredentialsPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest, memberRequest: vi.fn() }));

const PLAN = {
  plan: null, trial_ends_at: null, read_only_reason: null, resources: [], warnings: [], hosted: false,
  platform_switches: { email: true, sms: false, whatsapp: true, native_push: true, wallet: true },
  platform_resources: [
    { key: "platform_email_monthly", label: "email", used: 120, limit: 500, unit: "count", percent: 24, level: "ok" },
    { key: "platform_sms_monthly", label: "sms", used: 50, limit: 50, unit: "count", percent: 100, level: "limit" },
  ],
};
let channels: object[] = [];

function mount(modules = ["email", "sms", "whatsapp", "mobile"], walletOn = true) {
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === "PATCH") return {};
    if (path.endsWith("/hosting-plan")) return PLAN;
    if (path.endsWith("/channels")) return { count: channels.length, next: null, previous: null, results: channels };
    if (path.endsWith("/api-settings")) return { email_provider_configured: false, smtp_host: "smtp.example.org" };
    if (path.endsWith("/wallet-credentials")) return { apple: { configured: false }, google: { configured: false }, effective: { apple: "platform", google: null } };
    return {};
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/m/lab/admin/settings/channels"]}>
      <PlatformCredentialsPanel makerspaceId={5} enabledModules={modules} walletOn={walletOn} />
    </MemoryRouter></QueryClientProvider>);
}
const rowOf = (name: string) => screen.getByText(name, { selector: "p" }).closest("li") as HTMLElement;
const patches = () => staffRequest.mock.calls.filter(([, init]) => init?.method === "PATCH").map(([path, init]) => [path, JSON.parse(init.body)]);

beforeEach(() => { staffRequest.mockReset(); channels = []; });

describe("platform credentials switches (decision 281)", () => {
  it("lists every integration with its switch, own-credential state and platform use", async () => {
    mount();
    const email = await waitFor(() => rowOf("Email"));
    await waitFor(() => expect(within(email).getByText("Own credentials set")).toBeInTheDocument());
    expect(within(email).getByText(/Platform use this month: 120 of 500/)).toBeInTheDocument();
    expect(within(email).getByRole("switch", { name: /Use the platform's credentials when this space has none: Email/ })).toBeChecked();
    expect(within(email).getByRole("link", { name: "Set under Email sending." })).toHaveAttribute("href", "/m/lab/admin/settings/email");
    const sms = rowOf("Text messages");
    expect(within(sms).getByRole("switch")).not.toBeChecked();
    expect(within(sms).getByText("Platform allowance used up")).toBeInTheDocument();
    expect(within(rowOf("App push")).getByText("Always sent through the Space Works app.")).toBeInTheDocument();
    expect(within(rowOf("Wallet passes")).getByText("No own credentials")).toBeInTheDocument();
    expect(screen.getByText(/own credentials always come first and are never limited/)).toBeInTheDocument();
  });

  it("creates a missing channel row with today's defaults when switching the platform fallback off", async () => {
    mount();
    const email = await waitFor(() => rowOf("Email"));
    await waitFor(() => expect(within(email).getByRole("switch")).toBeEnabled());
    fireEvent.click(within(email).getByRole("switch"));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0]).toEqual(["/integrations/makerspace/5/channels/email", { enabled: true, personal_enabled: true, use_platform_sender: false }]);
  });

  it("sends only the switch for an existing row, and the wallet switch to the wallet endpoint", async () => {
    channels = [{ channel: "whatsapp", enabled: true, room_enabled: false, personal_enabled: false, provider: "meta", credentials_set: true }];
    mount();
    const whatsapp = await waitFor(() => rowOf("WhatsApp"));
    await waitFor(() => expect(within(whatsapp).getByText("Own credentials set")).toBeInTheDocument());
    fireEvent.click(within(whatsapp).getByRole("switch"));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0]).toEqual(["/integrations/makerspace/5/channels/whatsapp", { use_platform_sender: false }]);
    fireEvent.click(within(rowOf("Wallet passes")).getByRole("switch"));
    await waitFor(() => expect(patches()).toHaveLength(2));
    expect(patches()[1]).toEqual(["/admin/makerspaces/5/wallet-credentials", { use_platform_credentials: false }]);
  });

  it("asks before switching a sender that people connected to for personal messages", async () => {
    channels = [{ channel: "sms", enabled: true, room_enabled: false, personal_enabled: true, provider: "twilio", credentials_set: false }];
    mount();
    const sms = await waitFor(() => rowOf("Text messages"));
    await waitFor(() => expect(within(sms).getByRole("switch")).toBeEnabled());
    fireEvent.click(within(sms).getByRole("switch"));
    expect(await screen.findByRole("dialog", { name: "Change the sender?" })).toBeInTheDocument();
    expect(patches()).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Change sender" }));
    await waitFor(() => expect(patches()[0]).toEqual(["/integrations/makerspace/5/channels/sms", { use_platform_sender: true }]));
  });

  it("shows only the integrations whose module or capability is on", async () => {
    mount(["email"], false);
    await waitFor(() => rowOf("Email"));
    expect(screen.queryByText("Text messages", { selector: "p" })).toBeNull();
    expect(screen.queryByText("Wallet passes", { selector: "p" })).toBeNull();
  });
});
