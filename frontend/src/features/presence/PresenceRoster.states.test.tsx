import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api/errors";
import { PresenceRoster } from "./PresenceRoster";

// MOD-3 flow audit: the staff roster's loading / empty / error / failed-action states.
const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest: api.staffRequest }));

const wrap = (ui: ReactNode) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>;
const row = { account_id: 41, display_name: "Asha Rao", role_label: "Member", status: "working", project_id: null, hide_on_display: false,
  started_at: new Date(Date.now() - 3_600_000).toISOString(), expires_at: new Date(Date.now() + 3_600_000).toISOString(),
  ended_at: null, end_reason: "", active: true, names_displayed: true, personal_opt_out_allowed: true };

beforeEach(() => api.staffRequest.mockReset());

describe("PresenceRoster states", () => {
  it("shows the empty state, and plural-correct zero count, when nobody is checked in", async () => {
    api.staffRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    render(wrap(<PresenceRoster makerspaceId={5} />));
    expect(await screen.findByText("No one is checked in")).toBeInTheDocument();
    expect(screen.getByText("0 people checked in now.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Check out/ })).not.toBeInTheDocument();
  });

  it("announces a permission refusal on check-out as an alert and keeps the person listed", async () => {
    api.staffRequest.mockImplementation(async (path: string) => {
      if (String(path ?? "").endsWith("/check-out")) throw new StructuredApiError(403, { code: "presence_permission_denied", detail: "Presence permission is required here." });
      return { count: 1, next: null, previous: null, results: [row] };
    });
    render(wrap(<PresenceRoster makerspaceId={5} />));
    fireEvent.click((await screen.findAllByRole("button", { name: "Check out Asha Rao" }))[0]);
    expect(await screen.findByText("Presence permission is required here.")).toBeInTheDocument();
    expect(screen.getAllByText("Asha Rao").length).toBeGreaterThan(0);
  });

  it("keeps the person listed and shows an alert when check-out fails", async () => {
    api.staffRequest.mockImplementation(async (path: string) => {
      if (String(path ?? "").endsWith("/check-out")) throw Object.assign(new Error("boom"), { status: 500 });
      return { count: 1, next: null, previous: null, results: [row] };
    });
    render(wrap(<PresenceRoster makerspaceId={5} />));
    fireEvent.click((await screen.findAllByRole("button", { name: "Check out Asha Rao" }))[0]);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText("Asha Rao").length).toBeGreaterThan(0));
  });

  it("renders RTL and emoji names unchanged", async () => {
    api.staffRequest.mockResolvedValue({ count: 1, next: null, previous: null, results: [{ ...row, display_name: "مريم 🚀" }] });
    render(wrap(<PresenceRoster makerspaceId={5} />));
    expect((await screen.findAllByText("مريم 🚀")).length).toBeGreaterThan(0);
  });
});
