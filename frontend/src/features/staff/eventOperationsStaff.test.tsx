import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest, StructuredApiError } from "../../lib/api";
import { EventDeleteDraft } from "./EventDeleteDraft";
import { SavedViewsMenu } from "./SavedViewsMenu";
import { StaffListContext } from "./StaffListContext";
import type { StaffEvent } from "./eventsApiTypes";
vi.mock("../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../lib/api")>(), staffRequest: vi.fn() }));
const client = () => new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

const draftEvent = { id: 12, title: "Soldering night", status: "draft", registration_counts: { pending_approval: 0, registered: 0, waitlisted: 0, rejected: 0, cancelled: 0, attended: 0 } } as unknown as StaffEvent;

describe("delete draft (B9)", () => {
  it("asks first, deletes the empty draft and closes", async () => {
    vi.mocked(staffRequest).mockResolvedValue(undefined);
    const deleted = vi.fn();
    render(<QueryClientProvider client={client()}><EventDeleteDraft event={draftEvent} makerspaceId={3} onDeleted={deleted} /></QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Delete draft…" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete draft" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/events/12/", { method: "DELETE" }));
    await waitFor(() => expect(deleted).toHaveBeenCalled());
  });
  it("explains a refusal and is absent once published", async () => {
    vi.mocked(staffRequest).mockRejectedValue(new StructuredApiError(409, { detail: "Only an empty draft can be deleted." }));
    const { rerender } = render(<QueryClientProvider client={client()}><EventDeleteDraft event={draftEvent} makerspaceId={3} onDeleted={vi.fn()} /></QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Delete draft…" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete draft" }));
    expect(await screen.findByText(/can't be deleted\. Cancel it instead\./)).toBeInTheDocument();
    rerender(<QueryClientProvider client={client()}><EventDeleteDraft event={{ ...draftEvent, status: "published" }} makerspaceId={3} onDeleted={vi.fn()} /></QueryClientProvider>);
    expect(screen.queryByRole("button", { name: "Delete draft…" })).not.toBeInTheDocument();
  });
});

describe("event saved views (B25)", () => {
  const view = { id: 5, owner_username: "manager", name: "No-shows", state: { status: "registered", event: "12" }, shared: false };
  const mount = () => {
    const restore = vi.fn();
    render(<QueryClientProvider client={client()}><StaffListContext.Provider value={{ ownerName: "manager", canShare: false }}>
      <SavedViewsMenu makerspaceId={3} entity="event_guests" state={{ status: "waitlisted" }} onRestore={restore} eventId={12}
        presets={[{ key: "waitlisted", label: "Waitlisted", filters: { status: "waitlisted" }, count: 4 }]} linkPrefix="guests-" />
    </StaffListContext.Provider></QueryClientProvider>);
    return restore;
  };
  it("keeps views per event, offers counted presets and saves the event with the view", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ count: 1, next: null, previous: null, results: [view] });
    const restore = mount();
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/saved-views?entity=event_guests&event=12&page=1"));
    fireEvent.click(screen.getByRole("button", { name: "Views" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Waitlisted (4)" }));
    expect(restore).toHaveBeenCalledWith({ status: "waitlisted" });
    fireEvent.click(screen.getByRole("button", { name: "Views" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Save current view…" }));
    fireEvent.change(screen.getByLabelText("View name"), { target: { value: "Waiting" } });
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    await waitFor(() => expect(vi.mocked(staffRequest).mock.calls.some(([, options]) => options?.method === "POST")).toBe(true));
    const post = vi.mocked(staffRequest).mock.calls.find(([, options]) => options?.method === "POST")!;
    expect(JSON.parse(String(post[1]?.body)).state).toEqual({ status: "waitlisted", event: "12" });
  });
  it("renames a view from Manage views", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ count: 1, next: null, previous: null, results: [view] });
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Views" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Manage views…" }));
    fireEvent.click(await screen.findByRole("button", { name: "Rename No-shows" }));
    fireEvent.change(screen.getByLabelText("New name for No-shows"), { target: { value: "Did not come" } });
    fireEvent.click(screen.getByRole("button", { name: "Save name" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/saved-views/5", { method: "PATCH", body: JSON.stringify({ name: "Did not come" }) }));
  });
});
