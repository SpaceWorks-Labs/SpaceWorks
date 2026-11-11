import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { presenceKeys, type PresenceSession } from "./api";
import { PresencePanel } from "./PresencePanel";
import { renewPhase } from "./renewReminder";

const api = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), memberRequest: api.memberRequest }));

const MIN = 60_000;
function session(overrides: Partial<PresenceSession> = {}): PresenceSession {
  return { started_at: new Date(Date.now() - 30 * MIN).toISOString(), expires_at: new Date(Date.now() + 90 * MIN).toISOString(),
    ended_at: null, end_reason: "", active: true, status: "visiting", project_id: null, hide_on_display: false,
    names_displayed: true, personal_opt_out_allowed: true, ...overrides };
}
const wrap = (ui: ReactNode) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>;
const renderPanel = (enabled = true) => render(wrap(<PresencePanel enabled={enabled} slug="lab" spaceName="Lab" member selfCheckIn />));
let current: unknown;

beforeEach(() => {
  api.memberRequest.mockReset();
  api.memberRequest.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.endsWith("/current")) return current;
    if (path.endsWith("/current/renew")) return session({ expires_at: new Date(Date.now() + 120 * MIN).toISOString() });
    if (path.endsWith("/current/end") && options?.method === "POST") return { active: false, session: null };
    throw new Error(`unexpected ${path}`);
  });
});
afterEach(() => { vi.unstubAllGlobals(); });

describe("renewPhase", () => {
  const at = (minutes: number, extra: Partial<PresenceSession> = {}) => ({ expires_at: new Date(Date.now() + minutes * MIN).toISOString(), ended_at: null, end_reason: "", ...extra });
  it("prompts within ten minutes of expiry and for ten minutes after", () => {
    expect(renewPhase(at(45), Date.now())).toBe("none");
    expect(renewPhase(at(8), Date.now())).toBe("soon");
    expect(renewPhase(at(-4), Date.now())).toBe("expired");
    expect(renewPhase(at(-15), Date.now())).toBe("gone");
  });
  it("never offers renewal after the person or staff ended the session", () => {
    expect(renewPhase(at(30, { ended_at: new Date().toISOString(), end_reason: "user_ended" }), Date.now())).toBe("gone");
  });
  it("matches the server's inclusive ten-minute grace boundary", () => {
    const now = Date.now();
    const expires_at = new Date(now - 10 * MIN).toISOString();
    expect(renewPhase({ expires_at, ended_at: expires_at, end_reason: "expired" }, now)).toBe("expired");
    expect(renewPhase({ expires_at, ended_at: expires_at, end_reason: "expired" }, now + 1)).toBe("gone");
  });
});

describe("PresencePanel", () => {
  it("renders nothing and sends no request when the presence module is off", () => {
    const { container } = renderPanel(false);
    expect(container).toBeEmptyDOMElement();
    expect(api.memberRequest).not.toHaveBeenCalled();
  });

  it("shows the current session with time left, status and the display disclosure", async () => {
    current = { active: true, session: session({ personal_opt_out_allowed: false }), presets: [60, 120, 180, 240] };
    renderPanel();
    expect(await screen.findByText("Checked in")).toBeInTheDocument();
    expect(screen.getByText("Visiting")).toBeInTheDocument();
    expect(screen.getByText(/1 h 30 min left|1 h 29 min left/)).toBeInTheDocument();
    expect(screen.getByText(/This space shows everyone's name and doesn't offer hiding/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("marks an event-assigned status as read-only", async () => {
    current = { active: true, session: session({ status: "attending_event" }) };
    renderPanel();
    expect(await screen.findByText("Attending an event")).toBeInTheDocument();
    expect(screen.getByText(/set by your event ticket check-in/)).toBeInTheDocument();
  });

  it("prompts to renew near expiry and renews from now by the chosen preset", async () => {
    current = { active: true, session: session({ expires_at: new Date(Date.now() + 6 * MIN).toISOString() }), presets: [60, 120, 180, 240] };
    renderPanel();
    const prompt = await screen.findByRole("alert");
    expect(prompt).toHaveTextContent(/Your check-in ends in [56] min/);
    fireEvent.click(screen.getByRole("button", { name: "Renew 2 hours" }));
    await waitFor(() => expect(api.memberRequest).toHaveBeenCalledWith("/public/lab/presence-sessions/current/renew", expect.objectContaining({ method: "POST", body: JSON.stringify({ duration_minutes: 120 }) })));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });

  it("shows a web notification once when the user granted it", async () => {
    const shown = vi.fn();
    class FakeNotification { static permission = "granted"; static requestPermission = vi.fn(); constructor(title: string, options: NotificationOptions) { shown(title, options); } }
    vi.stubGlobal("Notification", FakeNotification);
    current = { active: true, session: session({ expires_at: new Date(Date.now() + 5 * MIN).toISOString() }) };
    const view = renderPanel();
    await waitFor(() => expect(shown).toHaveBeenCalledTimes(1));
    expect(shown.mock.calls[0][0]).toBe("Lab: check-in ending");
    view.rerender(wrap(<PresencePanel enabled slug="lab" spaceName="Lab" member selfCheckIn />));
    expect(shown).toHaveBeenCalledTimes(1);
  });

  it("offers to enable device notifications without asking unprompted", async () => {
    const requestPermission = vi.fn(async () => "granted");
    vi.stubGlobal("Notification", class { static permission = "default"; static requestPermission = requestPermission; });
    current = { active: true, session: session() };
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Notify me before it ends" }));
    await waitFor(() => expect(requestPermission).toHaveBeenCalledTimes(1));
  });

  it("keeps an expired session renewable inside the grace window", async () => {
    current = { active: true, session: session({ expires_at: new Date(Date.now() - 3 * MIN).toISOString() }) };
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent(/Your check-in ended at/);
    expect(screen.getByRole("button", { name: "Check in again" })).toBeInTheDocument();
  });

  it.each([false, true])("hydrates a renewable expired session on reopening (swept: %s)", async (swept) => {
    const expires = new Date(Date.now() - 3 * MIN).toISOString();
    current = { active: false, session: null, renewable: session({ active: false, expires_at: expires,
      ended_at: swept ? expires : null, end_reason: swept ? "expired" : "" }), presets: [60, 120] };
    const view = renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent(/Your check-in ended at/);
    view.unmount();
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent(/Your check-in ended at/);
    expect(screen.queryByText("Checked in")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Renew 2 hours" }));
    await waitFor(() => expect(api.memberRequest).toHaveBeenCalledWith(
      "/public/lab/presence-sessions/current/renew", expect.objectContaining({ body: JSON.stringify({ duration_minutes: 120 }) })));
    expect(await screen.findByText("Checked in")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "End check-in" }));
    expect(await screen.findByText("You're not checked in.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Renew 2 hours" })).not.toBeInTheDocument();
  });

  it("withdraws the renewal prompt when the server no longer offers a renewable session", async () => {
    current = { active: false, session: null, renewable: session({ active: false,
      expires_at: new Date(Date.now() - 3 * MIN).toISOString(), end_reason: "expired" }) };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><PresencePanel enabled slug="lab" spaceName="Lab" member selfCheckIn /></QueryClientProvider>);
    expect(await screen.findByRole("alert")).toHaveTextContent(/Your check-in ended at/);
    current = { active: false, session: null, renewable: null };
    await act(async () => { await client.invalidateQueries({ queryKey: presenceKeys.member("lab") }); });
    expect(await screen.findByText("You're not checked in.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Renew 1 hour" })).not.toBeInTheDocument();
  });

  it("does not invent expired history when the server returns no renewable session", async () => {
    current = { active: false, session: null, renewable: null };
    renderPanel();
    expect(await screen.findByText("You're not checked in.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a server refusal when a hydrated session loses renewal authority", async () => {
    current = { active: false, session: null, renewable: session({ active: false,
      expires_at: new Date(Date.now() - 3 * MIN).toISOString() }) };
    api.memberRequest.mockImplementation(async (path: string) => {
      if (path.endsWith("/current")) return current;
      throw new Error("Staff ended this check-in.");
    });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Renew 1 hour" }));
    expect(await screen.findByText("Staff ended this check-in.")).toBeInTheDocument();
    expect(screen.queryByText("Checked in")).not.toBeInTheDocument();
  });

  it("ends the session and returns to the check-in state", async () => {
    current = { active: true, session: session() };
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "End check-in" }));
    expect(await screen.findByText("You're not checked in.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check in" })).toBeInTheDocument();
  });

  it("opens the check-in sheet when not checked in", async () => {
    current = { active: false, session: null, presets: [60, 120, 180, 240] };
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Check in" }));
    expect(screen.getByRole("dialog", { name: "Check in" })).toBeInTheDocument();
  });
});
