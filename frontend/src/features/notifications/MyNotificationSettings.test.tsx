import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { MyNotificationSettings } from "./MyNotificationSettings";

// MOD-3B frontend states: loading, error + retry, permission denied, empty offer, module-off channels, OAuth return.
const h = vi.hoisted(() => ({
  preferences: { isLoading: false, error: null as unknown, data: undefined as unknown, refetch: vi.fn() },
  endpoints: { error: null as unknown, data: undefined as unknown },
  returned: { error: null as unknown, data: undefined as unknown },
  verify: { mutate: vi.fn(), isError: false, isSuccess: false, error: null as unknown },
  install: { mutate: vi.fn(), isError: false, isSuccess: false, error: null as unknown },
  sms: { error: null as unknown, data: undefined as unknown },
  oauthState: vi.fn(),
}));
vi.mock("./channelsApi", () => ({
  usePreferences: () => h.preferences, useEndpoints: () => h.endpoints,
  useOAuthReturn: (...args: unknown[]) => { h.oauthState(...args); return h.returned; }, useVerifyChallenge: () => h.verify,
}));
vi.mock("./smsConsentApi", () => ({ useSmsConsent: () => h.sms }));
vi.mock("./SlackInstallation", () => ({ slackInstallKey: (id: number) => `slack-install:${id}`, useCompleteSlackInstall: () => h.install }));
vi.mock("./SmsConsent", () => ({ SmsConsent: () => <p>sms-consent</p> }));
vi.mock("./ChannelDeliveryLog", () => ({ ChannelDeliveryLog: ({ title }: { title: string }) => <h3>{title}</h3> }));
vi.mock("./PersonalChannels", () => ({
  connectedChannels: (rows?: { channel: string; effective_valid?: boolean }[]) => new Set((rows ?? []).filter(r => r.effective_valid).map(r => r.channel)),
  PersonalChannels: ({ channels }: { channels: string[] }) => <ul aria-label="offered">{channels.map(c => <li key={c}>{c}</li>)}</ul>,
}));
vi.mock("./ChannelPreferences", () => ({
  ChannelPreferences: ({ preferences, connected }: { preferences: unknown[]; connected: Set<string> }) =>
    <p data-testid="prefs">{preferences.length} rows, connected: {[...connected].sort().join(",") || "none"}</p>,
}));

const row = (feature: string, available_channels: string[]) => ({ feature, available_channels });
function Search() { return <output data-testid="search">{useLocation().search}</output>; }
function show(path = "/", member = false) {
  return render(<MemoryRouter initialEntries={[path]}><MyNotificationSettings makerspaceId={4} member={member} /><Search /></MemoryRouter>);
}

beforeEach(() => {
  Object.assign(h.preferences, { isLoading: false, error: null, data: { preferences: [row("hardware_requests", ["telegram", "email"])] } });
  h.preferences.refetch.mockReset();
  Object.assign(h.endpoints, { error: null, data: { results: [] } });
  Object.assign(h.returned, { error: null, data: undefined });
  Object.assign(h.verify, { isError: false, isSuccess: false, error: null });
  Object.assign(h.install, { isError: false, isSuccess: false, error: null });
  Object.assign(h.sms, { error: null, data: undefined });
  h.verify.mutate.mockReset(); h.install.mutate.mockReset(); h.oauthState.mockReset();
  sessionStorage.clear();
});

describe("MyNotificationSettings states", () => {
  it("loading: announces the loading label and renders none of the sections", () => {
    h.preferences.isLoading = true;
    show();
    expect(screen.getByText("Loading your notification settings…")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Notification choices" })).not.toBeInTheDocument();
  });

  it("error: shows the failure with a Retry button that refetches", () => {
    h.preferences.error = new Error("Server unreachable");
    show();
    expect(screen.getByRole("alert")).toHaveTextContent("Server unreachable");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(h.preferences.refetch).toHaveBeenCalledTimes(1);
  });

  it("permission denied (403): the refusal message is shown and no setting is rendered", () => {
    h.preferences.error = new StructuredApiError(403, { detail: "Personal notifications are turned off.", code: "module_disabled" });
    show();
    expect(screen.getByRole("alert")).toHaveTextContent("Personal notifications are turned off.");
    expect(screen.queryByText("sms-consent")).not.toBeInTheDocument();
  });

  it("no data and no error still falls back to the generic error with retry", () => {
    h.preferences.data = undefined;
    show();
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load your notification settings.");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("module-off / nothing offered: no connectable chat channel is listed, only the sections remain", () => {
    h.preferences.data = { preferences: [row("hardware_requests", ["email"])] };
    show();
    expect(screen.getByRole("list", { name: "offered" })).toBeEmptyDOMElement();
    expect(screen.getByTestId("prefs")).toHaveTextContent("1 rows, connected: none");
    expect(screen.getByRole("heading", { name: "Recent deliveries" })).toBeInTheDocument();
  });

  it("empty preferences: renders the sections with zero rows", () => {
    h.preferences.data = { preferences: [] };
    show();
    expect(screen.getByTestId("prefs")).toHaveTextContent("0 rows");
  });

  it("offers a channel the server offers, plus one already connected even if no longer offered; revoked ones are not", () => {
    h.preferences.data = { preferences: [row("hardware_requests", ["slack"])] };
    h.endpoints.data = { results: [
      { channel: "telegram", revoked_at: null, effective_valid: true },
      { channel: "discord", revoked_at: "2026-11-01T00:00:00Z", effective_valid: false },
    ] };
    show();
    expect([...screen.getAllByRole("listitem")].map(li => li.textContent)).toEqual(["telegram", "slack"]);
    expect(screen.getByTestId("prefs")).toHaveTextContent("connected: telegram");
  });

  it("a failed endpoints request does not hide the page: nothing is treated as connected", () => {
    h.endpoints.error = new Error("endpoints down");
    h.endpoints.data = undefined;
    show();
    expect(screen.getByTestId("prefs")).toHaveTextContent("connected: none");
  });

  it("SMS counts as connected only when available, consented, verified and not suppressed", () => {
    const sms = (over: object) => ({ sms: { available: true, consented: true, phone_verified: true, suppressed: false, ...over } });
    h.sms.data = sms({});
    const view = show();
    expect(screen.getByTestId("prefs")).toHaveTextContent("connected: sms");
    view.unmount();
    h.sms.data = sms({ suppressed: true });
    show();
    expect(screen.getByTestId("prefs")).toHaveTextContent("connected: none");
  });

  it("an OAuth return verifies the challenge once and strips the return params, keeping the member section", async () => {
    h.returned.data = { oauth_return: { challenge_id: 31 } };
    show("/?code=c1&state=s1&section=preferences", true);
    await waitFor(() => expect(h.verify.mutate).toHaveBeenCalledTimes(1));
    expect(h.verify.mutate).toHaveBeenCalledWith({ challengeId: 31, code: "c1", state: "s1" });
    expect(screen.getByTestId("search")).toHaveTextContent("?section=channels");
  });

  it("a Slack install return (staff only) completes the install instead of verifying a challenge", async () => {
    sessionStorage.setItem("slack-install:4", "s9");
    show("/?code=c9&state=s9");
    await waitFor(() => expect(h.install.mutate).toHaveBeenCalledWith({ code: "c9", state: "s9" }));
    expect(h.verify.mutate).not.toHaveBeenCalled();
    expect(h.oauthState).toHaveBeenLastCalledWith(4, null, false);
    expect(screen.getByTestId("search")).toHaveTextContent(/^$/);
  });

  it("reports connect, verify and install outcomes as status or alert messages", () => {
    Object.assign(h.returned, { error: new Error("bad state") });
    Object.assign(h.verify, { isError: true, error: new Error("code rejected") });
    Object.assign(h.install, { isError: true, error: new Error("slack refused") });
    show();
    const alerts = screen.getAllByRole("alert").map(node => node.textContent);
    expect(alerts).toEqual([
      "Couldn't validate the connection return: bad state",
      "Couldn't finish connecting: code rejected",
      "Couldn't install Slack: slack refused",
    ]);
  });

  it("verify and install success show a status line", () => {
    Object.assign(h.verify, { isSuccess: true });
    Object.assign(h.install, { isSuccess: true });
    show();
    expect(screen.getAllByRole("status").map(node => node.textContent).filter(Boolean)).toEqual([
      "Connected.", "Slack app installed. You can now enable personal messages in channel settings."]);
  });
});
