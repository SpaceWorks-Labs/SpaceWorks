import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setRouteSessionContext } from "../../lib/api/sessionContext";

import { ChannelSetupPanel } from "./ChannelSetupPanel";
import type { Channel } from "./channelsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest, memberRequest: vi.fn(), getAccessToken: () => null }));

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });
const telegram: Channel = { channel: "telegram", enabled: true, room_enabled: true, personal_enabled: false, provider: "telegram",
  email_fallback: true, integration_identity: "lab_bot", generation: 3, quotas: {}, credentials_set: true, templates: [] };
let rows: Channel[] = [];

function route(path: string, init?: RequestInit) {
  if (path.endsWith("/channels")) return Promise.resolve(page(rows));
  if (path.includes("/channels/")) return Promise.resolve({ ...telegram, ...JSON.parse(String(init?.body ?? "{}")), credentials: undefined });
  if (path.endsWith("/installation")) return Promise.resolve({ generation: 4, configured: true });
  if (path.endsWith("/personal/endpoints")) return Promise.resolve(page([]));
  if (path.endsWith("/notification-destinations")) return Promise.resolve([{ id: 9, channel: "telegram", label: "Desk", is_active: true }]);
  if (path.endsWith("/channels-test")) return Promise.resolve({ accepted: false, provider_id: "", retryable: false, error_code: "not_configured", sanitized_error: "not_configured" });
  return Promise.reject(new Error(`unexpected ${path}`));
}

// R4 audit B (#183B): a channel whose module is off is not listed, so the default world installs them all.
const ALL = ["notifications", "email", "telegram", "slack", "mattermost", "discord", "sms", "whatsapp", "mobile"];
function mount(modules = ALL) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <ChannelSetupPanel makerspaceId={5} enabledModules={modules} /></QueryClientProvider>);
}
const open = async (label: string) => fireEvent.click(await screen.findByRole("button", { name: new RegExp(`^${label}`) }));
const patches = () => staffRequest.mock.calls.filter(([, init]) => init?.method === "PATCH").map(([path, init]) => [path, JSON.parse(init.body)]);

beforeEach(() => {
  setRouteSessionContext("person"); sessionStorage.clear();
  rows = []; staffRequest.mockReset(); staffRequest.mockImplementation(route);
});
afterEach(() => { setRouteSessionContext("person"); sessionStorage.clear(); });

describe("Space Manager channel setup", () => {
  it.each([
    ["SMS", "sms", "twilio", "status_url", "Status callback URL"],
    ["WhatsApp", "whatsapp", "twilio", "inbound_url", "Inbound callback URL"],
    ["WhatsApp", "whatsapp", "meta", "webhook_url", "Meta webhook URL"],
  ] as const)("copies saved %s %s provider callback URLs", async (label, channel, provider, key, fieldLabel) => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    const url = `https://api.example.test/signed/${provider}/7/callback`;
    rows = [{ ...telegram, channel, provider, room_enabled: false, callback_urls: { [key]: url } }];
    mount(["sms", "whatsapp"]);
    await open(label);
    expect(screen.getByLabelText(fieldLabel)).toHaveValue(url);
    fireEvent.click(screen.getByRole("button", { name: `Copy ${fieldLabel}` }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(url));
    expect(await screen.findByText(`${fieldLabel} copied.`)).toBeInTheDocument();
  });

  it("refreshes callback URLs after saving a rotated generation", async () => {
    rows = [{ ...telegram, channel: "whatsapp", provider: "twilio", room_enabled: false,
      callback_urls: { inbound_url: "https://api.example.test/2/inbound" } }];
    staffRequest.mockImplementation((path, init) => String(path).endsWith("/channels/whatsapp")
      ? Promise.resolve({ ...rows[0], generation: 4, callback_urls: { inbound_url: "https://api.example.test/4/inbound" } })
      : route(path, init));
    mount(["whatsapp"]);
    await open("WhatsApp");
    expect(screen.getByLabelText("Inbound callback URL")).toHaveValue("https://api.example.test/2/inbound");
    fireEvent.click(screen.getByRole("button", { name: "Save WhatsApp" }));
    await waitFor(() => expect(screen.getByLabelText("Inbound callback URL")).toHaveValue("https://api.example.test/4/inbound"));
  });

  it("offers a provider approval refresh for saved Twilio templates", async () => {
    const whatsapp: Channel = { ...telegram, channel: "whatsapp", provider: "twilio", room_enabled: false,
      templates: [{ event: "notification_opt_in", audience: "member", locale: "en", template_name: "HX123", variables: ["code"], approved: false }] };
    rows = [whatsapp];
    staffRequest.mockImplementation((path, init) => {
      if (String(path).endsWith("/templates/refresh")) {
        whatsapp.templates[0].approved = true;
        return Promise.resolve({ checked: 1, approved: 1, unavailable: 0 });
      }
      if (String(path).endsWith("/channels/whatsapp")) return Promise.resolve(whatsapp);
      return route(path, init);
    });
    mount();
    await open("WhatsApp");
    fireEvent.click(screen.getByRole("button", { name: "Refresh approval" }));
    expect(await screen.findByText("1 of 1 templates approved.")).toBeInTheDocument();
    expect(screen.getByText("Approved")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Template name"), { target: { value: "HXchanged" } });
    expect(screen.getByRole("button", { name: "Refresh approval" })).toBeDisabled();
  });
  it("lists every medium with its state", async () => {
    rows = [telegram];
    mount();
    const list = within(await screen.findByRole("list", { name: "Notification channels" }));
    for (const name of ["Email", "Telegram", "Slack", "Mattermost", "Discord", "SMS", "WhatsApp", "App push"]) {
      expect(list.getByRole("button", { name: new RegExp(`^${name}`) })).toBeInTheDocument();
    }
    expect(list.getByRole("button", { name: /^Telegram/ })).toHaveTextContent("On · rooms");
    expect(list.getByRole("button", { name: /^Slack/ })).toHaveTextContent("Not set up");
  });

  it("creates an unconfigured channel with today's behaviour, never switching rooms off", async () => {
    mount();
    await open("Slack");
    expect(screen.getByText(/Not set up yet/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save Slack" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0]).toEqual(["/integrations/makerspace/5/channels/slack", { enabled: true, room_enabled: true, personal_enabled: false }]);
  });

  it("never resends provider, identity or credentials for an unrelated toggle", async () => {
    rows = [telegram];
    mount();
    await open("Telegram");
    fireEvent.click(screen.getByRole("checkbox", { name: /Staff rooms/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save Telegram" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0][1]).toEqual({ enabled: true, personal_enabled: false, room_enabled: false });
  });

  it("requires every credential before replacing them and warns that people must reconnect", async () => {
    rows = [telegram];
    mount();
    await open("Telegram");
    expect(screen.getByText(/Credentials are saved and never shown again/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Bot username"), { target: { value: "new_bot" } });
    expect(screen.getByText("Saving reconnects this channel.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Bot token"), { target: { value: " 123:abc " } });
    fireEvent.click(screen.getByRole("button", { name: "Save Telegram" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0][1]).toMatchObject({ integration_identity: "new_bot", credentials: { bot_token: "123:abc" } });
    expect(screen.getByLabelText("Bot token")).toHaveValue("");
  });

  it("refuses personal delivery before the integration identity is set", async () => {
    mount();
    await open("Discord");
    fireEvent.click(screen.getByRole("checkbox", { name: /Personal messages/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save Discord" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter every required credential before turning on personal messages.");
    expect(patches()).toHaveLength(0);
  });

  it("sets WhatsApp up with the Meta provider, partial credentials refused, and template bindings", async () => {
    mount();
    await open("WhatsApp");
    const form = within(screen.getByRole("form", { name: "WhatsApp settings" }));
    fireEvent.change(form.getByLabelText("Provider"), { target: { value: "meta" } });
    fireEvent.change(form.getByLabelText("App ID"), { target: { value: "1" } });
    fireEvent.click(form.getByRole("button", { name: "Save WhatsApp" }));
    expect(form.getByRole("alert")).toHaveTextContent(/Enter every required credential/);
    for (const [label, value] of [["App secret", "s"], ["WhatsApp Business Account ID", "b"], ["Phone number ID", "p"],
      ["Permanent access token", "t"], ["Webhook verify token", "v"]]) fireEvent.change(form.getByLabelText(label), { target: { value } });
    fireEvent.click(form.getByRole("button", { name: "Add template" }));
    fireEvent.change(form.getByLabelText("Event"), { target: { value: "request_accepted" } });
    fireEvent.change(form.getByLabelText("Template name"), { target: { value: "accepted_v1" } });
    fireEvent.change(form.getByLabelText("Variables (comma separated)"), { target: { value: "name, item" } });
    fireEvent.click(form.getByRole("button", { name: "Save WhatsApp" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    const body = patches()[0][1];
    expect(body.provider).toBe("meta");
    expect(body.credentials).toEqual({ app_id: "1", app_secret: "s", business_account_id: "b",
      phone_number_id: "p", access_token: "t", webhook_verify_token: "v" });
    expect(body.templates).toEqual([{ event: "request_accepted", audience: "member", locale: "en", template_name: "accepted_v1", variables: ["name", "item"] }]);
    expect(body).not.toHaveProperty("room_enabled");
  });

  it.each(["twilio", "meta"])("uses canonical opt-in and test bindings for %s", async provider => {
    mount();
    await open("WhatsApp");
    const form = within(screen.getByRole("form", { name: "WhatsApp settings" }));
    fireEvent.change(form.getByLabelText("Provider"), { target: { value: provider } });
    fireEvent.click(form.getByRole("button", { name: "Add opt-in template" }));
    fireEvent.click(form.getByRole("button", { name: "Add test template" }));
    const groups = form.getAllByRole("group", { name: /^Template / });
    groups.forEach((group, index) => fireEvent.change(within(group).getByLabelText("Template name"), { target: { value: `approved_${index}` } }));
    expect(form.getByRole("button", { name: "Add opt-in template" })).toBeDisabled();
    expect(form.getByRole("button", { name: "Add test template" })).toBeDisabled();
    fireEvent.click(form.getByRole("button", { name: "Save WhatsApp" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0][1].templates).toEqual([
      { event: "notification_opt_in", audience: "member", locale: "en", template_name: "approved_0", variables: ["code"] },
      { event: "notification_test", audience: "member", locale: "en", template_name: "approved_1", variables: [] },
    ]);
  });

  it("keeps the tenant email fallback on the email channel", async () => {
    mount();
    await open("Email");
    fireEvent.click(screen.getByRole("checkbox", { name: /Email fallback/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save Email" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0][1]).toEqual({ enabled: true, personal_enabled: true, email_fallback: false });
  });

  it("does not list a channel whose module is off, and sends a sanitized room test", async () => {
    rows = [telegram];
    mount(["notifications"]);
    await screen.findByRole("list", { name: "Notification channels" });
    expect(screen.queryByRole("button", { name: /^Telegram/ })).toBeNull();
    cleanup();
    mount();
    await open("Telegram");
    fireEvent.click(await screen.findByRole("button", { name: "Send test" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Test failed: not_configured.");
    const call = staffRequest.mock.calls.find(([path]) => String(path).endsWith("/channels-test"))!;
    expect(JSON.parse(call[1].body)).toEqual({ channel: "telegram", room_id: 9 });
  });

  it("explains a refusal instead of hiding the section", async () => {
    staffRequest.mockImplementation(() => Promise.reject(new Error("Channel settings require a Space Manager.")));
    mount();
    expect(await screen.findByText(/Couldn't load channel settings/)).toBeInTheDocument();
  });

  it.each([
    ["Mattermost", { "Server URL": "https://chat.example/", "Bot token": "bot", "OAuth client ID": "a".repeat(26),
      "OAuth client secret": "secret", "Webhook token": "webhook" },
      { server_url: "https://chat.example/", bot_token: "bot", client_id: "a".repeat(26), client_secret: "secret", webhook_token: "webhook" }, "https://chat.example"],
    ["Discord", { "Bot token": "bot", "Application ID": "123", "OAuth client secret": "secret", "Public key": "a".repeat(64), "Server (guild) ID": "456" },
      { bot_token: "bot", application_id: "123", client_secret: "secret", public_key: "a".repeat(64), guild_id: "456" }, "123:456"],
  ] as const)("saves %s with adapter credential keys and derived identity", async (label, inputs, credentials, identity) => {
    mount();
    await open(label);
    for (const [name, value] of Object.entries(inputs)) fireEvent.change(screen.getByLabelText(name), { target: { value } });
    fireEvent.click(screen.getByRole("checkbox", { name: /Personal messages/ }));
    fireEvent.click(screen.getByRole("button", { name: `Save ${label}` }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0][1]).toMatchObject({ credentials, integration_identity: identity, personal_enabled: true });
    await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => String(path).endsWith(`/${label.toLowerCase()}/installation`))).toBe(true));
    const installed = staffRequest.mock.calls.find(([path]) => String(path).endsWith(`/${label.toLowerCase()}/installation`))!;
    expect(JSON.parse(installed[1].body)).toEqual(credentials);
  });

  it("includes Twilio's required HTTPS callback origin", async () => {
    mount();
    await open("WhatsApp");
    for (const [name, value] of Object.entries({ "WhatsApp sender number": "+14155550100", "Account SID": `AC${"a".repeat(32)}`,
      "Auth token": "b".repeat(32), "Public callback base URL": "https://api.example", "WhatsApp sender (optional)": "+14155550100" })) {
      fireEvent.change(screen.getByLabelText(name), { target: { value } });
    }
    fireEvent.click(screen.getByRole("button", { name: "Save WhatsApp" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0][1].credentials.public_base_url).toBe("https://api.example");
  });

  it("bootstraps Slack then starts the workspace installation instead of typing an identity", async () => {
    staffRequest.mockImplementation((path, init) => String(path).endsWith("/slack/install/start")
      ? Promise.resolve({ connect_url: "https://slack.com/oauth/v2/authorize?state=signed-install" }) : route(path, init));
    mount();
    await open("Slack");
    expect(screen.queryByLabelText("Workspace (team) ID")).toBeNull();
    for (const [name, value] of Object.entries({ "Client ID": "123", "Client secret": "secret", "Signing secret": "sign" }))
      fireEvent.change(screen.getByLabelText(name), { target: { value } });
    fireEvent.click(screen.getByRole("button", { name: "Save Slack" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0][1].credentials).toEqual({ client_id: "123", client_secret: "secret", signing_secret: "sign" });
    fireEvent.click(screen.getByRole("button", { name: "Install Slack app" }));
    expect(await screen.findByRole("link", { name: "Continue to Slack" })).toHaveAttribute("href", "https://slack.com/oauth/v2/authorize?state=signed-install");
    expect(sessionStorage.getItem("notification-slack-install:person:5")).toBe("signed-install");
    expect(sessionStorage.getItem("notification-slack-install:platform:5")).toBeNull();
  });
});


it("keeps SMS off by default and requires complete own credentials", async () => {
  mount(["sms"]);
  await open("SMS");
  expect(screen.getByRole("checkbox", { name: /Use SMS/ })).not.toBeChecked();
  fireEvent.change(screen.getByLabelText("Auth token"), { target: { value: "secret-token" } });
  fireEvent.click(screen.getByRole("button", { name: "Save SMS" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Enter every required credential");
  expect(patches()).toHaveLength(0);
  fireEvent.change(screen.getByLabelText("Account SID"), { target: { value: "AC" + "a".repeat(32) } });
  fireEvent.change(screen.getByLabelText("Sender phone number"), { target: { value: "+14155550101" } });
  fireEvent.click(screen.getByRole("button", { name: "Save SMS" }));
  await waitFor(() => expect(patches()).toHaveLength(1));
  expect(patches()[0]).toEqual(["/integrations/makerspace/5/channels/sms", {
    enabled: false, personal_enabled: false,
    credentials: { account_sid: "AC" + "a".repeat(32), auth_token: "secret-token", from_number: "+14155550101" },
  }]);
  expect(screen.getByLabelText("Auth token")).toHaveValue("");
});

it("requires explicit review to clear an imported sender hold without rotating credentials", async () => {
  rows = [{ ...telegram, channel: "sms", provider: "twilio", room_enabled: false, personal_enabled: true,
    activation_hold: true, use_platform_sender: false, sender_key: "twilio:account:number" }];
  mount(["sms"]);
  await open("SMS");
  expect(screen.getByText("Review needed")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Send test" })).toBeNull();
  expect(screen.getByLabelText("Auth token")).toHaveValue("");
  fireEvent.click(screen.getByRole("checkbox", { name: /I reviewed the imported sender/ }));
  fireEvent.click(screen.getByRole("button", { name: "Save SMS" }));
  await waitFor(() => expect(patches()).toHaveLength(1));
  expect(patches()[0][1]).toEqual({ enabled: true, personal_enabled: true, activation_hold: false });
});

it("makes platform fallback explicit and removes own credentials only when requested", async () => {
  rows = [{ ...telegram, channel: "sms", provider: "twilio", room_enabled: false, personal_enabled: true,
    use_platform_sender: false }];
  mount(["sms"]);
  await open("SMS");
  fireEvent.click(screen.getByRole("checkbox", { name: /Use the platform's credentials when this space has none/ }));
  fireEvent.click(screen.getByRole("checkbox", { name: /Remove saved own credentials/ }));
  fireEvent.click(screen.getByRole("button", { name: "Save SMS" }));
  await waitFor(() => expect(patches()).toHaveLength(1));
  expect(patches()[0][1]).toEqual({ enabled: true, personal_enabled: true, use_platform_sender: true, credentials: {} });
});

it("sends SMS diagnostics to the caller through the canonical endpoint only", async () => {
  rows = [{ ...telegram, channel: "sms", provider: "twilio", room_enabled: false, personal_enabled: true }];
  mount(["sms"]);
  await open("SMS");
  fireEvent.click(await screen.findByRole("button", { name: "Send test" }));
  await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => path.endsWith("/channels-test"))).toBe(true));
  const call = staffRequest.mock.calls.find(([path]) => path.endsWith("/channels-test"))!;
  expect(JSON.parse(call[1].body)).toEqual({ channel: "sms" });
  expect(staffRequest.mock.calls.some(([path]) => path.includes("messaging-settings"))).toBe(false);
});

it("preserves template feature binding and never submits browser approval", async () => {
  rows = [{ ...telegram, channel: "whatsapp", provider: "meta", room_enabled: false, templates: [{
    feature: "hardware_requests", event: "accepted", audience: "member", locale: "en", template_name: "accepted_v1",
    variables: ["request_id"], approved: true, needs_review: false,
  }] }];
  mount(["whatsapp"]);
  await open("WhatsApp");
  fireEvent.change(screen.getByLabelText("Template name"), { target: { value: "accepted_v2" } });
  fireEvent.click(screen.getByRole("button", { name: "Save WhatsApp" }));
  await waitFor(() => expect(patches()).toHaveLength(1));
  expect(patches()[0][1].templates).toEqual([{
    feature: "hardware_requests", event: "accepted", audience: "member", locale: "en", template_name: "accepted_v2", variables: ["request_id"],
  }]);
});
