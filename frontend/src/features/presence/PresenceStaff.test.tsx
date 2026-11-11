import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PresencePrivacySettings } from "./PresencePrivacySettings";
import { PresenceRoster } from "./PresenceRoster";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest: api.staffRequest }));

const wrap = (ui: ReactNode) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>;
const now = Date.now();
const row = { account_id: 41, display_name: "Asha Rao", role_label: "Member", status: "working", project_id: 3, hide_on_display: false,
  started_at: new Date(now - 3_600_000).toISOString(), expires_at: new Date(now + 3_600_000).toISOString(), ended_at: null, end_reason: "",
  active: true, names_displayed: true, personal_opt_out_allowed: true };
let privacy = { show_names: true, allow_personal_opt_out: true };

beforeEach(() => {
  privacy = { show_names: true, allow_personal_opt_out: true };
  api.staffRequest.mockReset();
  api.staffRequest.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.includes("/presence-sessions/current")) return { count: 1, next: null, previous: null, results: [row] };
    if (path.endsWith("/check-out")) return { active: false, session: null };
    if (path.endsWith("/check-in")) return { ...row, account_id: 52 };
    if (path.startsWith("/admin/memberships")) return { results: [{ id: 9, user: { id: 52, username: "ravi", display_name: "Ravi K" } }] };
    if (path.endsWith("/privacy")) {
      if (options?.method === "PATCH") privacy = { ...privacy, ...JSON.parse(String(options.body)) };
      return privacy;
    }
    throw new Error(`unexpected ${path}`);
  });
});

describe("PresenceRoster", () => {
  it("lists who is present now with status and times, and checks a person out", async () => {
    render(wrap(<PresenceRoster makerspaceId={5} />));
    expect((await screen.findAllByText("Asha Rao")).length).toBeGreaterThan(0);
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspace/5/presence-sessions/current?page=1");
    expect(screen.getAllByText("Working on a project").length).toBeGreaterThan(0);
    expect(screen.getByText("1 person checked in now.")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Check out Asha Rao" })[0]);
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspace/5/presence-sessions/check-out", expect.objectContaining({ method: "POST", body: JSON.stringify({ account_id: 41 }) })));
  });

  it("checks a member in on staff authority, without any location", async () => {
    render(wrap(<PresenceRoster makerspaceId={5} />));
    fireEvent.click(await screen.findByRole("button", { name: "Check someone in" }));
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "ra" } });
    fireEvent.click(await screen.findByRole("radio", { name: /Ravi K/ }));
    fireEvent.click(screen.getByRole("radio", { name: "1 h" }));
    fireEvent.click(screen.getByRole("button", { name: "Check in" }));
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspace/5/presence-sessions/check-in", expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(String(api.staffRequest.mock.calls.find(([path]) => String(path).endsWith("/check-in"))![1].body));
    expect(body).toEqual({ account_id: 52, duration_minutes: 60 });
  });
});

describe("PresencePrivacySettings", () => {
  it("saves show-names and the personal opt-out switch", async () => {
    render(wrap(<PresencePrivacySettings makerspaceId={5} />));
    const optOut = await screen.findByRole("switch", { name: "Let people hide their name" });
    fireEvent.click(optOut);
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspace/5/presence-sessions/privacy", expect.objectContaining({ method: "PATCH", body: JSON.stringify({ allow_personal_opt_out: false }) })));
    await waitFor(() => expect(screen.getByRole("switch", { name: "Let people hide their name" })).not.toBeChecked());
  });

  it("disables the opt-out switch while names are hidden for everyone", async () => {
    privacy = { show_names: false, allow_personal_opt_out: true };
    api.staffRequest.mockImplementation(async () => privacy);
    render(wrap(<PresencePrivacySettings makerspaceId={5} />));
    expect(await screen.findByRole("switch", { name: "Let people hide their name" })).toBeDisabled();
    expect(screen.getByText("Only applies while names are shown.")).toBeInTheDocument();
  });
});
