import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request }));
vi.mock("./eventWebsiteApi", () => ({ useEventWebsite: () => ({ data: { sections: [
  { kind: "speaker", slug: "ada", title: "Ada Lovelace" }, { kind: "faq", slug: "faq", title: "FAQ" },
] } }) }));

import { EventSpeakersPanel } from "./EventSpeakersPanel";

const linked = { id: 1, event_id: 4, display_name: "Grace Hopper", user: { id: 9, display_name: "Grace" }, section_slug: null,
  status: "linked", linked_via: "staff_assigned", grants_check_in: true, claim_expires_at: null, claimed_at: null, created_at: "2026-10-01T00:00:00Z", removed_at: null };
const invited = { ...linked, id: 2, display_name: "Ada Lovelace", user: null, status: "invited", linked_via: "", grants_check_in: false, claim_expires_at: "2026-10-30T00:00:00Z" };

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><EventSpeakersPanel eventId={4} makerspaceId={2} websiteEnabled /></QueryClientProvider>);
}

beforeEach(() => {
  request.mockReset();
  request.mockImplementation((path: string, options?: RequestInit) => {
    if (path.startsWith("/admin/events/4/speakers/?page=")) return Promise.resolve({ count: 2, next: null, previous: null, results: [linked, invited] });
    if (path.startsWith("/admin/events/4/speaker-candidates/")) return Promise.resolve({ results: [{ id: 33, display_name: "Alan Turing", username: "alan", relation: "member" }] });
    if (path === "/admin/events/4/speakers/invite/") return Promise.resolve({ speaker: invited, claim_url: "https://lab.test/m/lab/member/speaker-claim#token=secret" });
    if (path === "/admin/events/4/speakers/" && options?.method === "POST") return Promise.resolve(linked);
    if (path.endsWith("/remove/")) return Promise.resolve({ ...linked, status: "removed" });
    return Promise.resolve({});
  });
});

describe("event speakers", () => {
  it("lists speakers with their status", async () => {
    setup();
    const list = await screen.findByRole("list", { name: "Speakers" });
    expect(within(list).getByText("Grace Hopper")).toBeVisible();
    expect(within(list).getByText("Linked")).toBeVisible();
    expect(within(list).getByText("Invited")).toBeVisible();
    expect(within(list).getByText(/Can check people in/)).toBeVisible();
  });

  it("searches candidates only from two characters and assigns with check-in on by default", async () => {
    setup();
    const search = screen.getByRole("combobox", { name: "Speaker account" });
    fireEvent.focus(search);
    fireEvent.change(search, { target: { value: "a" } });
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(request.mock.calls.some(([path]) => String(path).includes("speaker-candidates"))).toBe(false);
    fireEvent.change(search, { target: { value: "al" } });
    const option = await screen.findByRole("option", { name: /Alan Turing/ });
    expect(request).toHaveBeenCalledWith("/admin/events/4/speaker-candidates/?search=al");
    fireEvent.mouseDown(option);
    const form = screen.getByRole("form", { name: "Assign a speaker" });
    expect(within(form).getByLabelText("Also allow check-in")).toBeChecked();
    fireEvent.change(within(form).getByLabelText("Website speaker profile (optional)"), { target: { value: "ada" } });
    fireEvent.click(within(form).getByRole("button", { name: "Assign speaker" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/events/4/speakers/", {
      method: "POST", body: JSON.stringify({ user_id: 33, grant_check_in: true, section_slug: "ada" }),
    }));
  });

  it("creates a claim link and shows it once with a copy button", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    setup();
    const form = screen.getByRole("form", { name: "Create a speaker claim link" });
    fireEvent.change(within(form).getByLabelText("Speaker name"), { target: { value: "Ada Lovelace" } });
    fireEvent.click(within(form).getByLabelText("Also allow check-in"));
    fireEvent.click(within(form).getByRole("button", { name: "Create claim link" }));
    expect(await screen.findByText("https://lab.test/m/lab/member/speaker-claim#token=secret")).toBeVisible();
    expect(request).toHaveBeenCalledWith("/admin/events/4/speakers/invite/", { method: "POST", body: JSON.stringify({ display_name: "Ada Lovelace", grant_check_in: false }) });
    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));
    await screen.findByText("Link copied.");
    expect(writeText).toHaveBeenCalledWith("https://lab.test/m/lab/member/speaker-claim#token=secret");
    fireEvent.click(screen.getByRole("button", { name: "Hide link" }));
    expect(screen.queryByText(/token=secret/)).toBeNull();
  });

  it("removes a speaker only after confirmation", async () => {
    setup();
    expect(screen.getByText(/Removing a speaker leaves their separate Team check-in grant active/)).toBeVisible();
    fireEvent.click(await screen.findByRole("button", { name: "Remove Grace Hopper" }));
    expect(within(screen.getByRole("dialog")).getByText(/Team check-in grant stays active; revoke check-in access on the Team tab/)).toBeVisible();
    expect(request.mock.calls.some(([path]) => String(path).endsWith("/remove/"))).toBe(false);
    fireEvent.click(await screen.findByRole("button", { name: "Remove speaker" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-speakers/1/remove/", { method: "POST", body: "{}" }));
  });
});
