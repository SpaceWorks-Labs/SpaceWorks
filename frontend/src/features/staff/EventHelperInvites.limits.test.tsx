import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { EventHelperInvites } from "./EventHelperInvites";
import { inviteLimitFromMine, inviteLimitInput, inviteLimitText } from "./EventInviteLimitFields";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request }));

const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
const limited = { id: 3, permissions: ["judge"], expires_at: "2999-01-01T00:00:00Z", redeemed_at: null, revoked_at: null,
  track_ids: [11], valid_from: null, valid_until: "2026-12-02T18:00:00Z" };
let refuse = false;

function show(myLimit: { track_ids: number[]; valid_from: string | null; valid_until: string | null } | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><EventHelperInvites eventId={5} held={["manage_team", "judge"]} myLimit={myLimit} /></QueryClientProvider>);
}

beforeEach(() => {
  refuse = false;
  request.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      if (refuse) throw new StructuredApiError(403, { detail: "An invitation cannot be wider than your own track or time limit." });
      return { id: 9, token: "tok" };
    }
    if (path.includes("/tracks/")) return page([{ id: 11, name: "Hardware" }, { id: 12, name: "Software" }]);
    return page(path.includes("staff-grants") ? [] : [limited]);
  });
});

it("sends a track and time limit, and lists each invitation's limit", async () => {
  show();
  expect(await screen.findByText(/Tracks: Hardware/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Invite email"), { target: { value: "judge@example.test" } });
  fireEvent.click(await screen.findByRole("checkbox", { name: "Software" }));
  fireEvent.change(screen.getByLabelText("Valid until"), { target: { value: "2026-12-02T18:00" } });
  fireEvent.click(screen.getByRole("button", { name: "Invite helper" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/events/5/staff-invites/", expect.objectContaining({ method: "POST" })));
  const body = JSON.parse(String(request.mock.calls.find(([, init]) => init?.method === "POST")?.[1]?.body));
  expect(body).toMatchObject({ permissions: ["judge"], track_ids: [12], valid_until: new Date("2026-12-02T18:00").toISOString() });
  expect(body).not.toHaveProperty("valid_from");
});

it("explains the 403 for an invitation wider than the inviter's own limit", async () => {
  refuse = true;
  show();
  fireEvent.change(await screen.findByLabelText("Invite email"), { target: { value: "judge@example.test" } });
  fireEvent.click(screen.getByRole("button", { name: "Invite helper" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("beyond your own track or time limit");
});

it("refuses an end before the start without sending", async () => {
  show();
  fireEvent.change(await screen.findByLabelText("Invite email"), { target: { value: "judge@example.test" } });
  fireEvent.change(screen.getByLabelText("Valid from"), { target: { value: "2026-12-02T18:00" } });
  fireEvent.change(screen.getByLabelText("Valid until"), { target: { value: "2026-12-01T18:00" } });
  fireEvent.click(screen.getByRole("button", { name: "Invite helper" }));
  expect(screen.getByRole("alert")).toHaveTextContent("The end must be after the start.");
  expect(request.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
});

it("prefills the form with the co-organizer's own track and window and sends it unchanged", async () => {
  show({ track_ids: [11], valid_from: null, valid_until: "2026-12-02T18:00:00Z" });
  expect(await screen.findByRole("checkbox", { name: "Hardware" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "Software" })).not.toBeChecked();
  expect(screen.getByLabelText("Valid until")).toHaveValue(inviteLimitFromMine({ track_ids: [], valid_from: null, valid_until: "2026-12-02T18:00:00Z" }).valid_until);
  expect(screen.getByText(/Filled in with your own track and time limit/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Invite email"), { target: { value: "judge@example.test" } });
  fireEvent.click(screen.getByRole("button", { name: "Invite helper" }));
  await waitFor(() => expect(request.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
  const body = JSON.parse(String(request.mock.calls.find(([, init]) => init?.method === "POST")?.[1]?.body));
  expect(body).toMatchObject({ track_ids: [11], valid_until: "2026-12-02T18:00:00.000Z" });
  expect(body).not.toHaveProperty("valid_from");
});

it("starts empty for an unlimited co-organizer", () => {
  expect(inviteLimitFromMine(null)).toEqual({ track_ids: [], valid_from: "", valid_until: "" });
});

it("leaves an empty limit to the server's inheritance", () => {
  expect(inviteLimitInput({ track_ids: [], valid_from: "", valid_until: "" })).toEqual({});
  expect(inviteLimitText({ track_ids: [], valid_from: null, valid_until: null })).toBe("");
});
