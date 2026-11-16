// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: MakerspaceMessagingSettings, messaging/messagingApi and messagingFixtures.messagingCatalog/messagingSettings are not in release 0.12.0.
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MakerspaceMessagingSettings } from "./MakerspaceMessagingSettings";
import { messagingCatalog, messagingFailure, messagingFetch, messagingSettings, renderMessaging } from "../../test/messagingFixtures";
import { expectNoA11yViolations } from "../../test/axe";
import { messagingSettingsKey } from "../messaging/messagingApi";
import { setAccessToken, clearAccessToken } from "../../lib/api";
import { setReauthenticationHandler } from "../../lib/api/reauthentication";

afterEach(() => { vi.unstubAllGlobals(); clearAccessToken(); });
const panel = <MakerspaceMessagingSettings makerspaceId={11} modules={["sms", "whatsapp"]} />;
const base = (url: URL) => url.pathname.endsWith("/catalog") ? messagingCatalog : messagingSettings;

it("keeps provider secrets write-only, shows sources, and copies exact callback values", async () => {
  messagingFetch(url => url.pathname.endsWith("/catalog") ? messagingCatalog : ({ ...messagingSettings, sms_auth_token: "must-never-render", whatsapp_access_token: "also-secret", whatsapp_app_secret: "app-secret" }));
  const copy = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal("navigator", { clipboard: { writeText: copy } });
  const { container } = renderMessaging(panel);
  await screen.findByText("SMS source: own");
  expect(screen.getByText("WhatsApp source: platform")).toBeInTheDocument();
  expect(screen.getByText("Twilio auth token: set. Leave blank to keep the saved value.")).toBeInTheDocument();
  for (const name of ["Twilio auth token", "WhatsApp access token", "WhatsApp app secret"]) {
    expect(screen.getByLabelText(name)).toHaveValue("");
    expect(screen.getByLabelText(name)).toHaveAttribute("type", "password");
  }
  expect(container.innerHTML).not.toMatch(/must-never-render|also-secret|app-secret/);
  for (const [label, value] of [
    ["SMS inbound URL", messagingSettings.webhook_urls.sms.inbound], ["SMS status URL", messagingSettings.webhook_urls.sms.status],
    ["WhatsApp callback URL", messagingSettings.webhook_urls.whatsapp.callback], ["Meta verify token", messagingSettings.whatsapp_webhook_verify_token],
  ]) {
    fireEvent.click(screen.getByRole("button", { name: `Copy ${label}` }));
    await waitFor(() => expect(copy).toHaveBeenLastCalledWith(value));
  }
  await expectNoA11yViolations(container);
});

it("saves only edited fields, clears secrets explicitly and invalidates only its key", async () => {
  const writes: Record<string, unknown>[] = [];
  let settings = { ...messagingSettings };
  messagingFetch((url, options) => {
    if (options.method === "PATCH") {
      const body = JSON.parse(String(options.body)); writes.push(body);
      settings = { ...settings, sms_auth_token_set: body.sms_auth_token !== "" };
    }
    return url.pathname.endsWith("/catalog") ? messagingCatalog : settings;
  });
  const { client } = renderMessaging(panel);
  await screen.findByLabelText("Twilio auth token");
  const invalidate = vi.spyOn(client, "invalidateQueries");
  fireEvent.change(screen.getByLabelText("Twilio auth token"), { target: { value: "replacement-secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Save messaging settings" }));
  await waitFor(() => expect(writes).toEqual([{ sms_auth_token: "replacement-secret" }]));
  await waitFor(() => expect(screen.getByLabelText("Twilio auth token")).toHaveValue(""));
  fireEvent.click(screen.getByRole("button", { name: "Clear Twilio auth token" }));
  await screen.findByText("Twilio auth token: not set. Leave blank to keep the saved value.");
  expect(writes[1]).toEqual({ sms_auth_token: "" });
  expect(invalidate.mock.calls.every(([filter]) => JSON.stringify(filter?.queryKey) === JSON.stringify(messagingSettingsKey(11)) && filter?.exact)).toBe(true);
  fireEvent.click(screen.getByLabelText("Use platform sender when no own sender is configured"));
  fireEvent.click(screen.getByRole("button", { name: "Save messaging settings" }));
  await waitFor(() => expect(writes[2]).toEqual({ use_platform_sender: false }));
});

it.each([
  [409, { code: "sender_in_use", detail: "Conflict" }, "This sender is already in use. Choose a different sender."],
  [400, { sms_from_number: ["Enter an E.164 number."] }, "Enter an E.164 number."],
] as const)("shows settings errors inline (%s)", async (status, body, text) => {
  messagingFetch((url, options) => options.method === "PATCH" ? messagingFailure(status, body) : base(url));
  renderMessaging(panel);
  fireEvent.change(await screen.findByLabelText("SMS from number (E.164)"), { target: { value: "invalid" } });
  fireEvent.click(screen.getByRole("button", { name: "Save messaging settings" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(text);
});

it("uses the shared recent reauthentication retry for credential changes", async () => {
  const payload = btoa(JSON.stringify({ user_id: 9, sid: "browser-session", surface: "staff" }));
  setAccessToken(`header.${payload}.signature`);
  let attempts = 0;
  const handler = vi.fn().mockResolvedValue(true);
  const removeHandler = setReauthenticationHandler(handler);
  messagingFetch((url, options) => {
    if (options.method === "PATCH" && ++attempts === 1) return messagingFailure(403, { code: "recent_reauth_required" });
    return base(url);
  });
  try {
    renderMessaging(panel);
    fireEvent.change(await screen.findByLabelText("Twilio auth token"), { target: { value: "new-token" } });
    fireEvent.click(screen.getByRole("button", { name: "Save messaging settings" }));
    await screen.findByText("Messaging settings saved.");
    expect(handler).toHaveBeenCalledTimes(1); expect(attempts).toBe(2);
  } finally { removeHandler(); }
});

it("shows none and platform unavailable and hides disabled channel controls", async () => {
  messagingFetch(url => url.pathname.endsWith("/catalog") ? messagingCatalog : { ...messagingSettings,
    effective_source: { sms: "none", whatsapp: "none" }, platform_available: { sms: false, whatsapp: false } });
  renderMessaging(<MakerspaceMessagingSettings makerspaceId={11} modules={["sms"]} />);
  await screen.findByText("SMS source: none");
  expect(screen.getByText("Platform SMS: unavailable")).toBeInTheDocument();
  expect(screen.queryByLabelText("WhatsApp access token")).not.toBeInTheDocument();
});

it("keeps unrelated unsaved settings when a credential is cleared", async () => {
  messagingFetch((url, options) => url.pathname.endsWith("/catalog") ? messagingCatalog
    : { ...messagingSettings, sms_auth_token_set: options.method !== "PATCH" });
  renderMessaging(panel);
  fireEvent.change(await screen.findByLabelText("WhatsApp phone number ID"), { target: { value: "987654" } });
  fireEvent.click(screen.getByRole("button", { name: "Clear Twilio auth token" }));
  await screen.findByText("Messaging settings saved.");
  expect(screen.getByLabelText("WhatsApp phone number ID")).toHaveValue("987654");
});

it("sends tests only to the caller and accurately reports queued, skipped, suppressed and HTTP errors", async () => {
  const bodies: unknown[] = [];
  const outcomes = [
    { delivery_id: 1, status: "pending", skip_reason: "" },
    { delivery_id: 2, status: "skipped", skip_reason: "phone_not_verified" },
    { delivery_id: 3, status: "suppressed", skip_reason: "" },
    messagingFailure(429, { detail: "Too many tests." }),
  ];
  messagingFetch((url, options) => {
    if (url.pathname.endsWith("/test")) { bodies.push(JSON.parse(String(options.body))); return outcomes.shift(); }
    return base(url);
  });
  renderMessaging(panel);
  await screen.findByRole("option", { name: "hardware_requests / accepted" });
  for (const [channel, text] of [["SMS", "Test queued; delivery is not yet confirmed."], ["WhatsApp", "Test skipped: phone_not_verified."], ["SMS", "Test suppressed."], ["SMS", "Too many tests."]]) {
    await waitFor(() => expect(screen.getByRole("button", { name: `Send ${channel} test` })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: `Send ${channel} test` }));
    await screen.findByText(text);
  }
  expect(bodies).toEqual(["sms", "whatsapp", "sms", "sms"].map(channel => ({ channel, feature: "hardware_requests", event: "accepted" })));
});

it("offers retry after a failed settings read", async () => {
  let failed = true;
  messagingFetch(url => failed ? messagingFailure(503, { detail: "Unavailable" }) : base(url));
  renderMessaging(panel);
  await screen.findByText("Couldn't load messaging settings. Try again.");
  failed = false;
  fireEvent.click(screen.getByRole("button", { name: /retry/i }));
  await screen.findByText("SMS source: own");
});
