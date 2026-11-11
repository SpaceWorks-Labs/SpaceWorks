import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { EventInductionPanel } from "./EventInductionPanel";
import { StaffListContext } from "./StaffListContext";

const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: mock.request }));

const event = { id: 4, status: "published" as const, starts_at: "2020-01-01T10:00:00Z" };
const overview = {
  links: [{ id: 1, event: 4, certification_type: 11, certification_type_name: "Laser basics", machine_type_id: 5, created_at: "" }],
  attendees: [
    { user_id: 21, name: "Ada", is_member: true, certified_type_ids: [] },
    { user_id: 22, name: "Grace", is_member: false, certified_type_ids: [] },
    { user_id: 23, name: "Linus", is_member: true, certified_type_ids: [11] },
  ],
  can_grant: true,
};

function show(features = ["machines.induction_events"], actions = ["manage_machines"], canLinkEvent = true) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actions }}>
      <EventInductionPanel makerspaceId={3} event={event} enabledFeatures={features} enabledModules={["machines", "events"]} canLinkEvent={canLinkEvent} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
}

beforeEach(() => {
  mock.request.mockReset();
  mock.request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === "/admin/makerspaces/3/events/4/induction" && !init?.method) return overview;
    if (path.startsWith("/admin/makerspace/3/certification-types")) return { count: 1, next: null, previous: null, results: [
      { id: 11, name: "Laser basics", is_active: true }, { id: 12, name: "Lathe", is_active: true }] };
    if (path === "/admin/makerspaces/3/events/4/induction/grant") return { results: [
      { user_id: 21, certification_type_id: 11, status: "granted", grant_id: 90, guest: false },
      { user_id: 22, certification_type_id: 11, status: "refused", code: "guest_pass_required" },
    ] };
    throw new Error(`unexpected ${path}`);
  });
});

it("stays hidden when the capability is off", () => {
  show([]);
  expect(mock.request).not.toHaveBeenCalled();
  expect(screen.queryByText("Induction")).not.toBeInTheDocument();
});

it("grants only checked-in attendees and reports a result per person", async () => {
  show();
  expect(await screen.findByText("Laser basics")).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: /Linus/ })).toBeDisabled();
  expect(await screen.findByRole("option", { name: "Lathe" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "Laser basics" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: /Ada/ }));
  fireEvent.click(screen.getByRole("checkbox", { name: /Grace/ }));
  fireEvent.click(screen.getByRole("button", { name: "Grant certification to 2 selected" }));
  await waitFor(() => expect(mock.request).toHaveBeenCalledWith("/admin/makerspaces/3/events/4/induction/grant",
    { method: "POST", body: JSON.stringify({ user_ids: [21, 22] }) }));
  expect(await screen.findByText(/Ada · Laser basics: Certified/)).toBeInTheDocument();
  expect(screen.getByText(/Grace · Laser basics: Not certified: not a member and holds no active guest pass/)).toBeInTheDocument();
});

it("offers Mark as induction only with authority on the event too (decision 224 b)", async () => {
  show(undefined, undefined, false);
  expect(await screen.findByText("Laser basics")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Mark as induction" })).not.toBeInTheDocument();
  expect(screen.getByText("Linking an induction also needs access to this event.")).toBeInTheDocument();
});

it("explains a 403 on linking as missing event access", async () => {
  const base = mock.request.getMockImplementation()!;
  mock.request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === "/admin/makerspaces/3/events/4/induction" && init?.method === "POST") throw new StructuredApiError(403, { detail: "Forbidden" });
    return base(path, init);
  });
  show();
  await screen.findByRole("option", { name: "Lathe" });
  fireEvent.change(screen.getByRole("combobox", { name: "Certification" }), { target: { value: "12" } });
  fireEvent.click(screen.getByRole("button", { name: "Mark as induction" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Linking an induction also needs access to this event.");
});
