import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api";

const { request, toast } = vi.hoisted(() => ({ request: vi.fn(), toast: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"), staffRequest: request }));
vi.mock("../../../components/ui/toastStore", async () => ({ ...await vi.importActual<typeof import("../../../components/ui/toastStore")>("../../../components/ui/toastStore"), toast }));

import { CheckInListsPanel, orderLists } from "./CheckInListsPanel";

const row = (id: number, position: number, extra = {}) => ({ id, event_id: 9, name: `List ${id}`, kind: "meal", after_entry: false, addon_id: null,
  addon_name: null, per_person: 1, archived: false, collected: 3, collected_people: 2, eligible: 10, position, ...extra });
const mount = (canManage = true) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
  <CheckInListsPanel eventId={9} canManage={canManage} addons={[]} /></QueryClientProvider>);
beforeEach(() => { request.mockReset(); toast.mockReset(); });

it("orders open lists by desk position and shows the counts", async () => {
  expect(orderLists([row(1, 2), row(2, 1), row(3, 0, { archived: true })]).map(item => item.id)).toEqual([2, 1, 3]);
  request.mockResolvedValue([row(1, 0), row(2, 1, { collected: 7, collected_people: 5 })]);
  mount();
  expect(await screen.findByText(/3 collected by 2 of 10 guests/)).toBeInTheDocument();
  expect(screen.getByText(/7 collected by 5 of 10 guests/)).toBeInTheDocument();
});

it("moves a list and restores an archived one", async () => {
  request.mockImplementation(async (path: string) => path.endsWith("/checkin-lists/") ? [row(1, 0), row(2, 1), row(3, 2, { archived: true })] : []);
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Move List 2 up" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/events/9/checkin-lists/reorder/", expect.objectContaining({ method: "POST", body: JSON.stringify({ ordered_ids: [2, 1] }) })));
  fireEvent.click(screen.getByRole("button", { name: "Restore" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/events/9/checkin-lists/3/", expect.objectContaining({ method: "PATCH", body: JSON.stringify({ restore: true }) })));
});

it("offers undo after a collection and an override for a waitlisted guest", async () => {
  let refuse = true;
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path.endsWith("/checkin-lists/")) return [row(1, 0)];
    if (path.endsWith("/scan/") && refuse) { refuse = false; throw new StructuredApiError(409, { code: "waitlisted", detail: "waitlisted" }); }
    if (path.endsWith("/scan/")) return { scan_id: 55, undo_until: new Date(Date.now() + 60_000).toISOString(), registration_id: 77, name: "Grace", allowed: 1, used: 1, reason: null, sent: JSON.parse(String(init?.body)) };
    return {};
  });
  mount(false);
  fireEvent.click(await screen.findByRole("button", { name: "Collect" }));
  fireEvent.change(screen.getByLabelText("Registration number"), { target: { value: "77" } });
  fireEvent.click(screen.getByRole("button", { name: "Record collection" }));
  fireEvent.click(await screen.findByRole("button", { name: "Let them collect anyway" }));
  await waitFor(() => expect(toast).toHaveBeenCalled());
  const scans = request.mock.calls.filter(([path]) => String(path).endsWith("/scan/"));
  expect(JSON.parse(String(scans[1][1]?.body))).toMatchObject({ registration_id: 77, override: true });
  const [message, options] = toast.mock.calls[0];
  expect(message).toBe("Grace collected from List 1.");
  await options.undo();
  expect(request).toHaveBeenCalledWith("/admin/events/9/checkin-lists/1/scan/55/undo/", { method: "POST", body: "{}" });
});
