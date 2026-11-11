import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AnnouncementsSection } from "./AnnouncementsSection";
import type { Announcement } from "./announcementsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest, publicV1Request: vi.fn() }));

const LIVE: Announcement = {
  id: 1, title: "Maintenance on Sunday", body: "Expect ten minutes of downtime.", severity: "maintenance", audience: "all_spaces",
  makerspaces: [], starts_at: "2026-11-01T00:00:00Z", ends_at: null, send_email: true, show_to_members: false, email_sent_at: "2026-11-01T00:01:00Z",
  email_recipient_count: 12, cancelled_at: null, created_by: "root", created_at: "2026-11-01T00:00:00Z", status: "live",
};

function setup() {
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") return LIVE;
    if (path.startsWith("/admin/platform/space-health")) return { count: 2, next: null, previous: null, results: [
      { id: 7, name: "North Lab" }, { id: 8, name: "South Lab" }] };
    return { count: 1, next: null, previous: null, results: [LIVE] };
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AnnouncementsSection /></QueryClientProvider>);
}

function posted(path: string) {
  const call = staffRequest.mock.calls.find(row => row[0] === path && (row[1] as RequestInit | undefined)?.method === "POST");
  return call ? JSON.parse((call[1] as RequestInit).body as string) : undefined;
}

beforeEach(() => { staffRequest.mockReset(); });

describe("AnnouncementsSection", () => {
  it("lists announcements with their status and email reach", async () => {
    setup();
    expect(await screen.findByText("Maintenance on Sunday")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText(/emailed to 12/)).toBeInTheDocument();
  });

  it("creates an announcement for selected spaces", async () => {
    setup();
    fireEvent.click(await screen.findByRole("button", { name: /New announcement/ }));
    const form = screen.getByRole("form", { name: "New announcement" });
    const publish = within(form).getByRole("button", { name: "Publish announcement" });
    fireEvent.change(within(form).getByRole("textbox", { name: "Title" }), { target: { value: "Policy update" } });
    fireEvent.change(within(form).getByRole("textbox", { name: /Message/ }), { target: { value: "New waiver from December." } });
    fireEvent.change(within(form).getByRole("combobox", { name: "Kind" }), { target: { value: "policy" } });
    fireEvent.change(within(form).getByRole("combobox", { name: "Audience" }), { target: { value: "selected_spaces" } });
    expect(publish).toBeDisabled();
    fireEvent.click(await within(form).findByRole("checkbox", { name: "South Lab" }));
    fireEvent.click(within(form).getByRole("checkbox", { name: "Show it to members too" }));
    fireEvent.click(publish);
    await waitFor(() => expect(posted("/admin/platform/announcements")).toMatchObject({ title: "Policy update", body: "New waiver from December.",
      severity: "policy", audience: "selected_spaces", makerspace_ids: [8], ends_at: null, send_email: false, show_to_members: true }));
    expect(posted("/admin/platform/announcements").starts_at).toMatch(/^\d{4}-\d\d-\d\dT/);
  });

  it("cancels a live announcement after confirming", async () => {
    setup();
    fireEvent.click(await screen.findByRole("button", { name: "Cancel Maintenance on Sunday" }));
    const dialog = await screen.findByRole("dialog", { name: "Cancel this announcement" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel announcement" }));
    await waitFor(() => expect(posted("/admin/platform/announcements/1/cancel")).toEqual({}));
  });
});
