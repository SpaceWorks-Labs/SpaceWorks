import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import { EventInductionPanel } from "./EventInductionPanel";
import { StaffListContext } from "./StaffListContext";
import type { InductionOverview } from "./eventInductionApi";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: request }));

const past = "2020-01-01T00:00:00Z";
const future = "2999-01-01T00:00:00Z";
const link = { id: 1, event: 5, certification_type: 10, certification_type_name: "Laser safety", machine_type_id: 2, created_at: past };
const overview = (over: Partial<InductionOverview> = {}): InductionOverview => ({ links: [link], can_grant: true, attendees: [
  { user_id: 1, name: "Asha Rao", is_member: true, certified_type_ids: [] }, { user_id: 2, name: "Gus Guest", is_member: false, certified_type_ids: [] },
  { user_id: 3, name: "Done Dee", is_member: true, certified_type_ids: [10] }], ...over });

let data: InductionOverview | Error;
let types: Array<{ id: number; name: string; is_active: boolean }>;
let grantResponse: unknown;
let actionError: Error | undefined;
let writes: Array<{ path: string; method: string; body?: Record<string, unknown> }>;

type PanelProps = Partial<Parameters<typeof EventInductionPanel>[0]>;
function mount(props: PanelProps = {}, context: { actions?: string[]; isSuperadmin?: boolean } = { actions: ["manage_machines"] }) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, ...context }}>
      <EventInductionPanel makerspaceId={3} event={{ id: 5, status: "published", starts_at: past }} enabledFeatures={["machines.induction_events"]} enabledModules={["machines", "events"]} canLinkEvent {...props} />
    </StaffListContext.Provider></QueryClientProvider>);
}
beforeEach(() => {
  data = overview(); types = [{ id: 10, name: "Laser safety", is_active: true }, { id: 11, name: "Router safety", is_active: true }, { id: 12, name: "Retired", is_active: false }];
  grantResponse = { results: [] }; actionError = undefined; writes = [];
  request.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method !== "GET") {
      writes.push({ path, method, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (actionError) throw actionError;
      return path.endsWith("/grant") ? grantResponse : {};
    }
    if (path.includes("certification-types")) return { results: types, next: null };
    if (data instanceof Error) throw data;
    return data;
  });
});

describe("visibility gates", () => {
  it.each([
    ["feature off", { enabledFeatures: [] }, { actions: ["manage_machines"] }],
    ["machines module off", { enabledModules: ["events"] }, { actions: ["manage_machines"] }],
    ["events module off", { enabledModules: ["machines"] }, { actions: ["manage_machines"] }],
    ["no machine authority", {}, { actions: ["manage_events"] }],
  ] as const)("renders nothing with %s", async (_name, props, context) => {
    const { container } = mount(props as PanelProps, context as never);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
    expect(request).not.toHaveBeenCalled();
  });
  it("a superadmin needs no listed action", async () => {
    mount({}, { isSuperadmin: true });
    expect(await screen.findByRole("heading", { name: "Induction" })).toBeInTheDocument();
  });
  it("renders nothing when the server refuses the overview (switched off or not a machine manager)", async () => {
    data = new StructuredApiError(404, { detail: "Not found", code: "not_found" });
    const { container } = mount();
    await waitFor(() => expect(request).toHaveBeenCalled());
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container.querySelector("section")).toBeNull();
  });
  it("shows a loading indicator first", () => {
    mount();
    expect(screen.getByText("Loading induction…")).toBeInTheDocument();
  });
  it("does not load anything while inactive", async () => {
    mount({ active: false });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(request).not.toHaveBeenCalled();
  });
});

describe("linking certifications", () => {
  it("lists linked certifications with a remove button that unlinks by link id", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Remove Laser safety" }));
    await waitFor(() => expect(writes[0]).toMatchObject({ path: "/admin/induction-links/1", method: "DELETE" }));
  });
  it("says it is not an induction yet when nothing is linked, and hides the attendee grid", async () => {
    data = overview({ links: [] });
    mount();
    expect(await screen.findByText("This event is not an induction yet.")).toBeInTheDocument();
    expect(screen.queryByText("Checked-in attendees")).toBeNull();
  });
  it("offers only active certifications not already linked, and links the chosen one", async () => {
    mount();
    const select = await screen.findByLabelText("Certification");
    await waitFor(() => expect(screen.getByRole("option", { name: "Router safety" })).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: "Laser safety" })).toBeNull();
    expect(screen.queryByRole("option", { name: "Retired" })).toBeNull();
    const mark = screen.getByRole("button", { name: "Mark as induction" });
    expect(mark).toBeDisabled();
    fireEvent.change(select, { target: { value: "11" } });
    fireEvent.click(mark);
    await waitFor(() => expect(writes[0]).toMatchObject({ path: "/admin/makerspaces/3/events/5/induction", method: "POST", body: { certification_type_id: 11 } }));
    await waitFor(() => expect(select).toHaveValue("0"));
  });
  it("without access to the event it explains instead of offering to link", async () => {
    mount({ canLinkEvent: false });
    expect(await screen.findByText("Linking an induction also needs access to this event.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Certification")).toBeNull();
  });
  it("a cancelled event offers no linking at all", async () => {
    mount({ event: { id: 5, status: "cancelled", starts_at: past } });
    await screen.findByRole("heading", { name: "Induction" });
    expect(screen.queryByLabelText("Certification")).toBeNull();
    expect(screen.queryByText("Linking an induction also needs access to this event.")).toBeNull();
  });
  it("maps a 403 on link to the event-access message", async () => {
    actionError = new StructuredApiError(403, { detail: "Forbidden", code: "forbidden" });
    mount();
    fireEvent.change(await screen.findByLabelText("Certification"), { target: { value: "0" } });
    await waitFor(() => expect(screen.getByRole("option", { name: "Router safety" })).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Certification"), { target: { value: "11" } });
    fireEvent.click(screen.getByRole("button", { name: "Mark as induction" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Linking an induction also needs access to this event.");
  });
});

describe("attendees and grants", () => {
  it("shows attendees with guest and already-certified markers; certified ones cannot be picked", async () => {
    mount();
    expect(await screen.findByText("Asha Rao")).toBeInTheDocument();
    expect(screen.getByText(/Gus Guest · guest/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Done Dee · already certified/)).toBeDisabled();
    expect(screen.getByRole("button", { name: "Grant certification to 0 selected" })).toBeDisabled();
  });
  it("explains that granting waits for the event to start, and keeps Grant disabled", async () => {
    mount({ event: { id: 5, status: "published", starts_at: future } });
    expect(await screen.findByText("Grant certifications once the event has started and attendees have checked in.")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/Asha Rao/));
    expect(screen.getByRole("button", { name: "Grant certification to 1 selected" })).toBeDisabled();
  });
  it("a draft event never counts as started", async () => {
    mount({ event: { id: 5, status: "draft", starts_at: past } });
    expect(await screen.findByText(/Grant certifications once the event has started/)).toBeInTheDocument();
  });
  it("says no one has checked in yet and shows no Grant button", async () => {
    data = overview({ attendees: [] });
    mount();
    expect(await screen.findByText("No one has checked in yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Grant certification/ })).toBeNull();
  });
  it("Grant stays disabled without grant authority", async () => {
    data = overview({ can_grant: false });
    mount();
    fireEvent.click(await screen.findByLabelText(/Asha Rao/));
    expect(screen.getByRole("button", { name: "Grant certification to 1 selected" })).toBeDisabled();
  });
  it("grants the picked people, shows per-person results, and offers Revoke only for a granted guest", async () => {
    grantResponse = { results: [
      { user_id: 1, certification_type_id: 10, status: "granted", guest: false, grant_id: 91 },
      { user_id: 2, certification_type_id: 10, status: "granted", guest: true, grant_id: 92 },
      { user_id: 3, certification_type_id: 10, status: "already_certified" },
      { user_id: 4, certification_type_id: 10, status: "refused", code: "guest_pass_required" },
    ] };
    mount();
    fireEvent.click(await screen.findByLabelText(/Asha Rao/));
    fireEvent.click(screen.getByLabelText(/Gus Guest/));
    fireEvent.click(screen.getByRole("button", { name: "Grant certification to 2 selected" }));
    await waitFor(() => expect(writes[0]).toMatchObject({ path: "/admin/makerspaces/3/events/5/induction/grant", method: "POST", body: { user_ids: [1, 2] } }));
    const results = await screen.findByRole("status", { name: "Grant results" });
    expect(results).toHaveTextContent("Asha Rao · Laser safety: Certified");
    expect(results).toHaveTextContent("Gus Guest · Laser safety: Certified (guest, valid while their pass lasts)");
    expect(results).toHaveTextContent("Done Dee · Laser safety: Already certified");
    expect(results).toHaveTextContent("#4 · Laser safety: Not certified: not a member and holds no active guest pass");
    expect(screen.getAllByRole("button", { name: "Revoke" })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Grant certification to 0 selected" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(writes[1]).toMatchObject({ path: "/admin/guest-certification-grants/92/revoke", method: "POST" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Revoke" })).toBeNull());
  });
  it("shows an unknown refusal code with the code, and falls back when there is none", async () => {
    grantResponse = { results: [{ user_id: 1, certification_type_id: 10, status: "refused", code: "weird" }, { user_id: 2, certification_type_id: 10, status: "refused" }] };
    mount();
    fireEvent.click(await screen.findByLabelText(/Asha Rao/));
    fireEvent.click(screen.getByRole("button", { name: "Grant certification to 1 selected" }));
    const results = await screen.findByRole("status", { name: "Grant results" });
    expect(results).toHaveTextContent("Not certified (weird)");
    expect(results).toHaveTextContent("Not certified (refused)");
  });
  it("shows a typed whole-request refusal for a grant before the event started", async () => {
    actionError = new StructuredApiError(409, { detail: "x", code: "event_not_started" });
    mount();
    fireEvent.click(await screen.findByLabelText(/Asha Rao/));
    fireEvent.click(screen.getByRole("button", { name: "Grant certification to 1 selected" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Certifications can be granted once the event has started.");
  });
  it("falls back to the server message, then to a generic one", async () => {
    actionError = new Error("Boom");
    mount();
    fireEvent.click(await screen.findByLabelText(/Asha Rao/));
    fireEvent.click(screen.getByRole("button", { name: "Grant certification to 1 selected" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Boom");
  });
  it("untoggling a picked person removes them from the grant", async () => {
    mount();
    const box = await screen.findByLabelText(/Asha Rao/);
    fireEvent.click(box);
    fireEvent.click(box);
    expect(screen.getByRole("button", { name: "Grant certification to 0 selected" })).toBeDisabled();
  });
});
