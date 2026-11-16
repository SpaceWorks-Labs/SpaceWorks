import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { StaffListContext } from "../../StaffListContext";
import { HandoverConsole } from "./HandoverConsole";
const { request, notify } = vi.hoisted(() => ({ request: vi.fn(), notify: vi.fn() }));
vi.mock("../../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../../lib/api")), staffRequest: request }));
vi.mock("../../../../components/ui/toastStore", () => ({ toast: notify }));
vi.mock("../shared", () => ({ useStaffGet: () => ({ data: [
  { id: 5, title: "Drill mount", requester_name: "Ada", completed_at: new Date(Date.now() - 86_400_000).toISOString(), machine: { name: "Printer" },
    payment: { id: 90, subject_type: "machine_service_request", status: "pending", amount: "12.00", currency: "usd" } },
  { id: 6, title: "Gear", requester_name: "Jo", payment: null, completed_at: new Date(Date.now() - 20 * 86_400_000).toISOString() },
], isLoading: false, isError: false }) }));
beforeEach(() => { request.mockReset(); request.mockResolvedValue({}); notify.mockReset(); });

function mount(actions: string[] = ["collect_service_request"]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}>
    <StaffListContext.Provider value={{ ownerName: "desk", canShare: false, actions, makerspace: { id: 1 } }}>
      <HandoverConsole makerspaceId={1} enabled />
    </StaffListContext.Provider></QueryClientProvider>);
  return { invalidate };
}

it("searches loaded requesters, shows unpaid money, and hands over through the collect dialog (MC3)", async () => {
  const { invalidate } = mount();
  expect(screen.getByRole("heading", { name: "Ready to collect", level: 1 })).toBeVisible();
  expect(screen.getByText("Unpaid USD 12.00")).toBeVisible();
  fireEvent.change(screen.getByRole("searchbox", { name: "Search by requester" }), { target: { value: "Ada" } });
  expect(screen.queryByText("Gear")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Hand over" }));
  fireEvent.change(screen.getByRole("textbox", { name: /Pickup code/ }), { target: { value: " 4821 " } });
  fireEvent.change(screen.getByRole("textbox", { name: /Collected by/ }), { target: { value: "Sam" } });
  fireEvent.click(screen.getByRole("button", { name: "Mark collected" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/machine-service/requests/5/collect",
    { method: "POST", body: JSON.stringify({ pickup_code: "4821", collector_name: "Sam" }) }));
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["machine-service-handover", 1] }));
  expect(notify).toHaveBeenCalledWith("Handed to Ada.");
});

it("says the charge is due when pay-before-pickup refuses, and offers no cash button without authority", async () => {
  const { StructuredApiError } = await vi.importActual<typeof import("../../../../lib/api")>("../../../../lib/api");
  request.mockRejectedValueOnce(new StructuredApiError(409, { detail: "This job's charge must be settled before pickup.", code: "payment_due" }));
  mount();
  fireEvent.click(screen.getAllByRole("button", { name: "Hand over" })[0]);
  fireEvent.click(screen.getByRole("button", { name: "Mark collected" }));
  expect(await screen.findByText(/must be paid before pickup/)).toBeVisible();
  expect(screen.queryByText(/may have been handed over already/)).toBeNull();
  expect(screen.queryByRole("button", { name: "Mark offline" })).toBeNull();
});

it("lets a desk holding record_payment record the job's cash on the row", () => {
  mount(["collect_service_request", "record_payment"]);
  expect(screen.getByRole("button", { name: "Mark offline" })).toBeVisible();
  // Waiving forgives debt: subject authority (manage_machines) only.
  expect(screen.queryByRole("button", { name: "Payment actions" })).toBeNull();
});

it("offers Not collected only after 14 days and posts the uncollected action", async () => {
  mount();
  expect(screen.queryByRole("button", { name: "More for Drill mount" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "More for Gear" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Mark not collected" }));
  fireEvent.click(screen.getByRole("button", { name: "Mark not collected" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/machine-service/requests/6/uncollected", { method: "POST", body: "{}" }));
});
