import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setRouteSessionContext } from "../../lib/api/sessionContext";

import { MyNotificationSettings } from "./MyNotificationSettings";
import type { Endpoint, Selection } from "./channelsApi";
import { connectedChannels } from "./PersonalChannels";

const { staffRequest, memberRequest } = vi.hoisted(() => ({ staffRequest: vi.fn(), memberRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest, memberRequest, getAccessToken: () => null }));

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });
const endpoint = (channel: Endpoint["channel"], id = 31): Endpoint => ({ id, channel, provider: "telegram", integration_generation: 1,
  verification_state: "verified", verified_at: "2026-10-16T10:00:00Z", consented_at: "2026-10-16T10:00:00Z", consent_version: "2026-10-16",
  revoked_at: null, created_at: "2026-10-16T10:00:00Z", effective_valid: true });
let endpoints: Endpoint[] = [];
let preferences: Selection[] = [];

function route(path: string, init?: RequestInit) {
  if (path === "/me/messaging?makerspace=8") return Promise.resolve({
    sms: { available: false, consented: false, phone_verified: false, phone_masked: "", suppressed: false },
    whatsapp: { available: false, consented: false, phone_verified: false, phone_masked: "", suppressed: false },
  });
  const base = "/integrations/makerspace/8/personal";
  if (path === `${base}/preferences` && init?.method === "PUT") {
    const edits: Selection[] = JSON.parse(String(init.body)).preferences;
    preferences = preferences.map(row => ({ ...row, ...edits.find(edit => edit.category === row.category) }));
    return Promise.resolve({ preferences });
  }
  if (path === `${base}/preferences`) return Promise.resolve({ preferences });
  if (path === `${base}/endpoints`) return Promise.resolve(page(endpoints));
  if (path.startsWith(`${base}/endpoints?oauth_state=`)) {
    const state = new URLSearchParams(path.split("?")[1]).get("oauth_state");
    return state === "s1" ? Promise.resolve({ ...page(endpoints), oauth_return: { challenge_id: 77, expires_at: "2099-01-01T00:00:00Z" } })
      : Promise.reject(new Error("Invalid OAuth state"));
  }
  if (path === `${base}/endpoints/start`) {
    const body = JSON.parse(String(init?.body));
    return Promise.resolve(body.channel === "telegram"
      ? { challenge_id: 77, expires_at: "2026-10-16T10:10:00Z", connect_url: "https://t.me/lab_bot?start=abc" }
      : { challenge_id: 78, expires_at: "2026-10-16T10:10:00Z", instructions: "We sent a code to your WhatsApp." });
  }
  if (path.startsWith(`${base}/challenges/`)) { endpoints = [endpoint(path.includes("/77/") ? "telegram" : "whatsapp")]; return Promise.resolve(endpoints[0]); }
  if (path.startsWith(`${base}/endpoints/`) && init?.method === "DELETE") { endpoints = []; return Promise.resolve({ revoked: true }); }
  if (path.startsWith(`${base}/deliveries`)) return Promise.resolve(page([{ id: 1, envelope_id: 2, channel: "telegram", state: "delivered",
    attempt_count: 1, next_attempt_at: null, last_error: "", retryable: false, event: "request_accepted", feature: "hardware_requests",
    created_at: "2026-10-16T10:00:00Z", updated_at: "2026-10-16T10:00:00Z" }]));
  return Promise.reject(new Error(`unexpected ${path}`));
}

function Location() { return <output data-testid="location">{useLocation().search}</output>; }
function mount(member = true, url = "/") {
  setRouteSessionContext(member ? "person" : "person");
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[url]}><MyNotificationSettings makerspaceId={8} member={member} /><Location /></MemoryRouter></QueryClientProvider>);
}
const sent = (mock: typeof memberRequest, suffix: string) => mock.mock.calls.filter(([path]) => String(path).endsWith(suffix));

beforeEach(() => {
  sessionStorage.clear();
  endpoints = [];
  preferences = [
    { category: "hardware_requests", channels: ["email", "in_app", "slack"], email_fallback: true, available_channels: ["email", "in_app", "telegram", "whatsapp"] },
    { category: "events", channels: ["email"], email_fallback: true, available_channels: ["email"] },
    { category: "printing", channels: ["email", "in_app"], email_fallback: true, available_channels: [] },
  ];
  for (const mock of [staffRequest, memberRequest]) { mock.mockReset(); mock.mockImplementation(route); }
});
afterEach(() => { setRouteSessionContext("person"); sessionStorage.clear(); });

describe("personal channel connections", () => {
  it("finishes a manager Slack installation through its authenticated callback", async () => {
    sessionStorage.setItem("notification-slack-install:person:8", "signed-install");
    sessionStorage.setItem("notification-slack-install:platform:8", "other-install");
    staffRequest.mockImplementation((path, init) => String(path).endsWith("/slack/oauth/callback")
      ? Promise.resolve({ verified: true }) : route(path, init));
    mount(false, "/?code=oauth-code&state=signed-install");
    expect(await screen.findByText(/Slack app installed/)).toBeInTheDocument();
    const calls = sent(staffRequest, "/slack/oauth/callback");
    expect(calls).toHaveLength(1);
    expect(JSON.parse(calls[0][1].body)).toEqual({ code: "oauth-code", state: "signed-install" });
    expect(sent(staffRequest, "/challenges/77/verify")).toHaveLength(0);
    expect(sessionStorage.getItem("notification-slack-install:person:8")).toBeNull();
    expect(sessionStorage.getItem("notification-slack-install:platform:8")).toBe("other-install");
  });
  it.each(["member", "platform", "staff:forge"])("does not complete a Slack installation saved by %s", async context => {
    sessionStorage.setItem(`notification-slack-install:${context}:8`, "signed-install");
    mount(false, "/?code=oauth-code&state=signed-install");
    await screen.findByText(/Couldn't validate the connection return/);
    expect(sent(staffRequest, "/slack/oauth/callback")).toHaveLength(0);
    expect(sessionStorage.getItem(`notification-slack-install:${context}:8`)).toBe("signed-install");
  });
  it("offers only the chat channels this space enabled", async () => {
    mount();
    const list = within(await screen.findByRole("list", { name: "Your connected channels" }));
    expect(list.getAllByRole("listitem").map(item => item.textContent)).toEqual([expect.stringContaining("Telegram"), expect.stringContaining("WhatsApp")]);
    expect(list.queryByText("Slack")).toBeNull();
  });

  it("connects Telegram through the bot deep link, then confirms", async () => {
    mount();
    fireEvent.click(within(await screen.findByRole("list", { name: "Your connected channels" })).getAllByRole("button", { name: "Connect" })[0]);
    const form = within(screen.getByRole("form", { name: "Connect Telegram" }));
    expect(form.getByRole("button", { name: "Connect Telegram" })).toBeDisabled();
    fireEvent.click(form.getByRole("checkbox"));
    fireEvent.click(form.getByRole("button", { name: "Connect Telegram" }));
    expect(await screen.findByRole("link", { name: /Open Telegram to connect/ })).toHaveAttribute("href", "https://t.me/lab_bot?start=abc");
    expect(JSON.parse(sent(memberRequest, "/endpoints/start")[0][1].body)).toEqual({ channel: "telegram", consent: true, consent_version: "2026-10-16" });
    fireEvent.click(screen.getByRole("button", { name: "I've connected" }));
    await waitFor(() => expect(sent(memberRequest, "/challenges/77/verify")).toHaveLength(1));
    expect(JSON.parse(sent(memberRequest, "/challenges/77/verify")[0][1].body)).toEqual({});
    expect(await screen.findByText("Connected")).toBeInTheDocument();
  });

  it("connects WhatsApp with a number and the code sent to it", async () => {
    mount();
    fireEvent.click(within(await screen.findByRole("list", { name: "Your connected channels" })).getAllByRole("button", { name: "Connect" })[1]);
    const form = within(screen.getByRole("form", { name: "Connect WhatsApp" }));
    fireEvent.change(form.getByLabelText("WhatsApp number"), { target: { value: "+44 7700 900123" } });
    fireEvent.click(form.getByRole("checkbox"));
    fireEvent.click(form.getByRole("button", { name: "Send me a code" }));
    expect(await screen.findByText("We sent a code to your WhatsApp.")).toBeInTheDocument();
    expect(JSON.parse(sent(memberRequest, "/endpoints/start")[0][1].body)).toMatchObject({ channel: "whatsapp", phone_number: "+447700900123" });
    fireEvent.change(screen.getByLabelText("Code"), { target: { value: " 123456 " } });
    fireEvent.click(screen.getByRole("button", { name: "Verify code" }));
    await waitFor(() => expect(sent(memberRequest, "/challenges/78/verify")).toHaveLength(1));
    expect(JSON.parse(sent(memberRequest, "/challenges/78/verify")[0][1].body)).toEqual({ code: "123456" });
  });

  it("disconnects a channel and staff use the staff client", async () => {
    endpoints = [endpoint("telegram")];
    mount(false);
    fireEvent.click(await screen.findByRole("button", { name: "Disconnect" }));
    await waitFor(() => expect(staffRequest.mock.calls.some(([path, init]) => path === "/integrations/makerspace/8/personal/endpoints/31" && init?.method === "DELETE")).toBe(true));
    expect(memberRequest).not.toHaveBeenCalled();
  });

  it.each([true, false])("finishes an OAuth return with code/state on the authenticated client (member=%s)", async member => {
    mount(member, "/?section=channels&notify_challenge=999&code=oauth-code&state=s1");
    const sender = member ? memberRequest : staffRequest;
    await waitFor(() => expect(sent(sender, "/challenges/77/verify")).toHaveLength(1));
    expect(sent(sender, "/challenges/77/verify")[0]).toEqual([
      "/integrations/makerspace/8/personal/challenges/77/verify",
      { method: "POST", body: JSON.stringify({ code: "oauth-code", state: "s1" }) },
    ]);
    expect(sender.mock.calls.some(([path]) => String(path).endsWith("/endpoints?oauth_state=s1"))).toBe(true);
    expect(member ? staffRequest : memberRequest).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("?section=channels"));
  });

  it("offers reconnect for a generation-invalidated endpoint and excludes it from choices", async () => {
    endpoints = [{ ...endpoint("telegram"), effective_valid: false }];
    expect(connectedChannels(endpoints).has("telegram")).toBe(false);
    mount();
    const list = within(await screen.findByRole("list", { name: "Your connected channels" }));
    expect(list.getByRole("button", { name: "Disconnect" })).toBeInTheDocument();
    expect(list.getAllByRole("button", { name: "Connect" })).toHaveLength(2);
    expect(screen.getByRole("checkbox", { name: "Hardware requests: Telegram" })).toBeDisabled();
  });

  it("never trusts an unbound challenge query from an OAuth return", async () => {
    mount(true, "/?notify_challenge=77&code=oauth-code&state=unknown");
    await screen.findByRole("list", { name: "Your connected channels" });
    expect(sent(memberRequest, "/challenges/77/verify")).toHaveLength(0);
  });

  it("uses the server's OAuth start data for same-tab provider navigation", async () => {
    preferences[0].available_channels = ["email", "discord"];
    memberRequest.mockImplementation((path, init) => String(path).endsWith("/endpoints/start")
      ? Promise.resolve({ challenge_id: 92, oauth_state: "signed-state", expires_at: new Date(Date.now() + 600000).toISOString(),
        connect_url: "https://discord.com/oauth2/authorize?state=signed-state" }) : route(path, init));
    mount();
    fireEvent.click(within(await screen.findByRole("list", { name: "Your connected channels" })).getByRole("button", { name: "Connect" }));
    const form = within(screen.getByRole("form", { name: "Connect Discord" }));
    fireEvent.click(form.getByRole("checkbox"));
    fireEvent.click(form.getByRole("button", { name: "Connect Discord" }));
    const link = await screen.findByRole("link", { name: /Open Discord/ });
    expect(link).toHaveAttribute("target", "_self");
    expect(link).toHaveAttribute("href", "https://discord.com/oauth2/authorize?state=signed-state");
  });
});

describe("per-category channel choice", () => {
  it("lists available categories, gates unconnected chat and saves only edited selections", async () => {
    endpoints = [endpoint("telegram")];
    mount();
    const form = within(await screen.findByRole("form", { name: "Where your notifications go" }));
    expect(form.queryByText("Printing")).toBeNull();
    expect(form.getByRole("checkbox", { name: "Hardware requests: WhatsApp" })).toBeDisabled();
    fireEvent.click(await form.findByRole("checkbox", { name: "Hardware requests: Telegram" }));
    fireEvent.click(form.getByRole("checkbox", { name: "Hardware requests: Email" }));
    fireEvent.click(form.getAllByRole("checkbox", { name: "Email me if none of these could deliver" })[0]);
    fireEvent.click(form.getByRole("button", { name: "Save choices" }));
    await waitFor(() => expect(sent(memberRequest, "/personal/preferences").some(([, init]) => init?.method === "PUT")).toBe(true));
    const put = sent(memberRequest, "/personal/preferences").find(([, init]) => init?.method === "PUT")!;
    expect(JSON.parse(put[1].body)).toEqual({ preferences: [
      { category: "hardware_requests", channels: ["in_app", "telegram"], email_fallback: false },
    ] });
  });

  it("shows the person's own delivery log", async () => {
    mount();
    const log = within(await screen.findByRole("region", { name: "Recent deliveries" }));
    expect(await log.findByText("Telegram")).toBeInTheDocument();
    expect(log.getByText("Delivered")).toBeInTheDocument();
  });
});
